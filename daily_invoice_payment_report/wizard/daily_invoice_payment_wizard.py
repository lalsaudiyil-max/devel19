from odoo import models, fields, api
from odoo.exceptions import UserError


class DailyInvoicePaymentWizard(models.TransientModel):
    _name = 'daily.invoice.payment.wizard'
    _description = 'Daily Invoice Payment Report'

    user_id = fields.Many2one('res.users', default=lambda self: self.env.user, required=True)
    date_from = fields.Date(default=fields.Date.context_today, required=True)
    date_to = fields.Date(default=fields.Date.context_today, required=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)

    def action_print(self):
        self.ensure_one()
        return self.env.ref(
            'daily_invoice_payment_report.action_report_daily_invoice_payment'
        ).report_action(self, data={
            'wizard_id': self.id,
            'date_from': str(self.date_from),
            'date_to': str(self.date_to),
        })


class ReportDailyInvoicePayment(models.AbstractModel):
    _name = 'report.daily_invoice_payment_report.daily_payment_report'
    _description = 'Abstract Daily Invoice Payment Report Engine'

    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env['daily.invoice.payment.wizard'].browse(data.get('wizard_id') or docids)
        
        # Identify the filtering user (fallback to the current env user if missing)
        target_user_id = wizard.user_id.id or self.env.user.id
        target_company_id = wizard.company_id.id or self.env.company.id
        target_user_name = wizard.user_id.name or self.env.user.name

        # 1. Invoices filtered by Date, State, Company, and Creator
        invoices = self.env['account.move'].search(
            [
                ('move_type', 'in', ['out_invoice', 'out_refund']),
                ('state', '=', 'posted'),
                ('invoice_date', '>=', wizard.date_from),
                ('invoice_date', '<=', wizard.date_to),
                ('company_id', '=', target_company_id),
                ('create_uid', '=', target_user_id),
            ],
            order='journal_id, invoice_date, name'
        )

        # 2. Payments filtered by Date, State, Company, and Creator
        payments = self.env['account.payment'].search([
            ('state', 'in', ['paid', 'in_process']),
            ('date', '>=', wizard.date_from),
            ('date', '<=', wizard.date_to),
            ('company_id', '=', target_company_id),
            ('create_uid', '=', target_user_id),
        ])

        def partner_type(p):
            if not p:
                return 'credit'
            tags = p.category_id.mapped('name')
            # Soft matching case-insensitive 'cash' check to handle 'Cash' or 'cash' tags
            return 'cash' if any('cash' in tag.lower() for tag in tags) else 'credit'

        invoice_data = {'cash': [], 'credit': []}
        invoice_by_journal = {}
        currency = self.env.company.currency_id

        for inv in invoices:
            t = partner_type(inv.partner_id)
            invoice_data[t].append(inv)
            journal_name = inv.journal_id.name or "Unknown Journal"
            if journal_name not in invoice_by_journal:
                invoice_by_journal[journal_name] = {
                    'cash_untaxed': 0.0,
                    'cash_tax': 0.0,
                    'cash_total': 0.0,

                    'credit_untaxed': 0.0,
                    'credit_tax': 0.0,
                    'credit_total': 0.0,

                    'untaxed': 0.0,
                    'tax': 0.0,
                    'total': 0.0,

                    'count': 0,
                }

            # totals by type
            #untaxed = 0.0
            #tax = 0.0
            #total = 0.0

            untaxed = inv.amount_untaxed_signed
            tax = inv.amount_tax_signed
            total = inv.amount_total_signed

                # final rounding at end
            #untaxed = float_round(untaxed, precision_digits=2)
            #tax = float_round(tax, precision_digits=2)
            #total = float_round(total, precision_digits=2)

            invoice_by_journal[journal_name][f'{t}_untaxed'] += untaxed
            invoice_by_journal[journal_name][f'{t}_tax'] += tax
            invoice_by_journal[journal_name][f'{t}_total'] += total

            # overall totals
            invoice_by_journal[journal_name]['untaxed'] += untaxed
            invoice_by_journal[journal_name]['tax'] += tax
            invoice_by_journal[journal_name]['total'] += total

            invoice_by_journal[journal_name]['count'] += 1
        for journal in invoice_by_journal.values():
            journal['cash_untaxed'] = currency.round(journal['cash_untaxed'])
            journal['cash_tax'] = currency.round(journal['cash_tax'])
            journal['cash_total'] = currency.round(journal['cash_total'])

            journal['credit_untaxed'] = currency.round(journal['credit_untaxed'])
            journal['credit_tax'] = currency.round(journal['credit_tax'])
            journal['credit_total'] = currency.round(journal['credit_total'])

            journal['untaxed'] = currency.round(journal['untaxed'])
            journal['tax'] = currency.round(journal['tax'])
            journal['total'] = currency.round(journal['total'])

        invoice_summary = {
            'cash_untaxed': sum(x.amount_untaxed_signed for x in invoice_data['cash']),
            'cash_tax': sum(x.amount_tax_signed for x in invoice_data['cash']),
            'cash_total': sum(x.amount_total_signed for x in invoice_data['cash']),

            'credit_untaxed': sum(x.amount_untaxed_signed for x in invoice_data['credit']),
            'credit_tax': sum(x.amount_tax_signed for x in invoice_data['credit']),
            'credit_total': sum(x.amount_total_signed for x in invoice_data['credit']),
        }

        t_payment_data = {'cash': {}, 'credit': {}}
        
        for pay in payments:
            inv = pay.reconciled_invoice_ids[:1]
            partner = inv.partner_id if inv else pay.partner_id
           

            if not partner:
                continue

            t = partner_type(partner)
            journal = pay.journal_id.name or "Unknown Journal"
            pay_date = str(pay.date)
            narration = pay.memo or "--"
            
            # Extract the customer name cleanly
            customer_name = partner.name or "Unknown Customer"

            # Create a unique composite key combining date, journal, customer, and memo 
            # to keep individual payment rows separate on the report
            t_payment_data[t].setdefault(pay_date, {})
            t_payment_data[t][pay_date].setdefault(journal, {})
            t_payment_data[t][pay_date][journal].setdefault(customer_name, {})
            t_payment_data[t][pay_date][journal][customer_name].setdefault(narration, 0.0)
            
            # Accumulate the amount for this specific transaction row
            t_payment_data[t][pay_date][journal][customer_name][narration] += pay.amount_signed
            

        # ============================================================
        # FLATTEN LIST FOR QWEB (Including Customer Name)
        # ============================================================
        payment_data = {'cash': [], 'credit': []}
        
        for p_type in ['cash', 'credit']:
            # Use raw keys to protect against mixed object types (date vs string) on staging
            for p_date in t_payment_data[p_type]:
                for journal_name in t_payment_data[p_type][p_date]:
                    for customer_name in t_payment_data[p_type][p_date][journal_name]:
                        for narration, amount_signed in t_payment_data[p_type][p_date][journal_name][customer_name].items():
                            
                            payment_data[p_type].append({
                                'date': p_date,
                                'journal': journal_name,
                                'customer': customer_name,
                                'memo': narration,
                                'amount': amount_signed,
                            })

        
        
        return {
            'doc_ids': docids,
            'doc_model': 'daily.invoice.payment.wizard',
            'docs': wizard,
            'date_from': data.get('date_from'),
            'date_to': data.get('date_to'),
            'target_user_name': target_user_name,
            'invoice_data': invoice_data,
            'invoice_summary': invoice_summary,
            'invoice_by_journal': invoice_by_journal,
            # Pass our new, easy-to-loop flat list structure straight to QWeb
            'payment_data': payment_data, 
        }
       
