from odoo import models, fields, api, _
from odoo.fields import Command
from odoo.exceptions import UserError


class TailoringInvoiceWizard(models.TransientModel):
    _name = 'tailoring.invoice.wizard'
    _description = 'ZATCA Reason Wizard'

    order_id = fields.Many2one('tailoring.order', string="Order", required=True)
    
    # Selection matched exactly to your ZATCA requirement
    l10n_sa_reason = fields.Selection([
        ('1', '[BR-KSA-17-reason-1] - Cancellation or suspension of the supplies after its occurrence either wholly or partially'),
        ('2', '[BR-KSA-17-reason-2] - In case of essential change or amendment in the supply, which leads to the change of the VAT due'),
        ('3', '[BR-KSA-17-reason-3] - Amendment of the supply value which is pre-agreed upon between the supplier and consumer'),
        ('4', '[BR-KSA-17-reason-4] - In case of goods or services refund'),
        ('5', '[BR-KSA-17-reason-5] - In case of change in Sellers or Buyers information')
    ], string="ZATCA Reason", required=True, default='2')

    def action_confirm(self):
        self.ensure_one()
        # Pass the reason through context so the main method can pick it up
        return self.order_id.with_context(l10n_sa_reason=self.l10n_sa_reason).action_create_invoice_confirmed()

class TailoringOrder(models.Model):
    _name = 'tailoring.order'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Tailoring Order'

    name = fields.Char("Order Ref", readonly=True, default='/')
    partner_id = fields.Many2one('res.partner', string="Customer", required=True)
    cutting_master_id = fields.Many2one('hr.employee', string="Cutting Master", tracking=True, ondelete='set null')
    
    state = fields.Selection([
        ('draft', 'Draft'), 
        ('confirmed', 'Confirmed'), 
        ('cut', 'Fabric Cut'), 
        ('done', 'Delivered')
    ], default='draft', tracking=True)
    
    line_ids = fields.One2many('tailoring.order.line', 'order_id')
    invoice_count = fields.Integer(compute="_compute_counts")
    purchase_order_count = fields.Integer(compute="_compute_counts")

    # --- NEW FINANCIAL FIELDS FOR DYNAMIC BILLING ---
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    amount_total = fields.Monetary(string='Total Amount', compute='_compute_amounts', store=True, currency_field='currency_id')
    amt_invoiced = fields.Monetary(string='Amount Billed', compute='_compute_amt_invoiced', store=False, currency_field='currency_id')
    amount_untaxed = fields.Monetary(string='Untaxed Amount', compute='_compute_amounts', store=True)
    amount_tax = fields.Monetary(string='Taxes', compute='_compute_amounts', store=True)
    # Balance field to show the Delta on the UI
    balance_due = fields.Monetary(string='Balance Due', compute='_compute_amounts')

    @api.depends('line_ids.price_subtotal', 'line_ids.price_tax', 'line_ids.price_total', 'amt_invoiced')
    def _compute_amounts(self):
        for order in self:
            order.amount_total = sum(order.line_ids.mapped('price_total'))
            order.amount_untaxed = sum(order.line_ids.mapped('price_subtotal'))
            order.amount_tax = sum(order.line_ids.mapped('price_tax'))
            order.balance_due = order.amount_total - order.amt_invoiced

    @api.depends('name')
    def _compute_amt_invoiced(self):
        for order in self:
        # Search for ALL invoices (Draft + Posted) linked to this order
            invoices = self.env['account.move'].search([
                ('tailoring_order_id', '=', order.id),
                ('state', 'in', ['draft', 'posted']), # Count draft so button hides early
                ('move_type', 'in', ['out_invoice', 'out_refund'])
                ])
        
            total = 0.0
            for inv in invoices:
                if inv.move_type == 'out_invoice':
                    total += inv.amount_total
                else:
                    total -= inv.amount_total
            order.amt_invoiced = total

    def _compute_counts(self):
        for o in self:
            o.invoice_count = self.env['account.move'].search_count([('invoice_origin', '=', o.name)])
            o.purchase_order_count = self.env['purchase.order'].search_count([('origin', '=', o.name)])

    def action_confirm(self):
        if self.name == '/':
            self.name = self.env['ir.sequence'].next_by_code('tailoring.order') or '/'
        self.write({'state': 'confirmed'})

    def action_view_invoices(self):
        return {
            'name': _('Invoices'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('invoice_origin', '=', self.name)],
            'context': {'default_move_type': 'out_invoice', 'default_invoice_origin': self.name}
        }

 # --- UPDATED CREATE INVOICE LOGIC ---
# --- UPDATED CREATE INVOICE LOGIC ---
    def action_create_invoice(self):
        self.ensure_one()
        invoice_lines = []
        refund_lines = []

        for line in self.line_ids.filtered(lambda l: not l.parent_line_id):
            # 1. Total current value (Parent + Children + Addons + VAT)
            current_suit_total = line.price_total 

            # 2. Amount already billed (Invoices minus Refunds)
            billed_lines = self.env['account.move.line'].search([
                ('tailoring_line_id', '=', line.id),
                ('move_id.state', 'in', ['draft', 'posted'])
            ])
        
            net_billed = 0.0
            for b_line in billed_lines:
                if b_line.move_id.move_type == 'out_invoice':
                    net_billed += b_line.price_total
                else:
                    net_billed -= b_line.price_total

            # 3. Calculate Delta
            delta = current_suit_total - net_billed

            if abs(delta) < 0.01:
                continue

            # 4. Prepare line values
            line_vals = {
                'product_id': line.product_id.id,
                'name': f"Adjustment for {line.product_id.name}",
                'quantity': 1.0,
                'price_unit': abs(delta) / 1.15 if line.tax_id else abs(delta),
                'tax_ids': [(6, 0, line.tax_id.ids)],
                'tailoring_line_id': line.id,
            }

            if delta > 0:
                invoice_lines.append((0, 0, line_vals))
            else:
                # We send the refund lines one by one or grouped by source invoice
                refund_lines.append((0, 0, line_vals))

        # 5. Execute Creation
        if invoice_lines:
            self._create_move('out_invoice', invoice_lines)
    
        if refund_lines:
            # FIX: We now process refunds by looking at the lines inside them
            self._create_refunds_with_correct_source(refund_lines)

        if not invoice_lines and not refund_lines:
            raise UserError(_("No financial changes detected to bill or refund."))

        return self.action_view_invoices()

    def _create_refunds_with_correct_source(self, refund_lines):
        """
        Groups refund lines by their original source invoice for ZATCA compliance.
        """
        # Dictionary to group lines: { invoice_id: [line_vals] }
        grouped_refunds = {}

        for line_tuple in refund_lines:
            line_vals = line_tuple[2]
            tailoring_line_id = line_vals.get('tailoring_line_id')
            
            # Find the specific original posted invoice for THIS item
            original_move_line = self.env['account.move.line'].search([
                ('tailoring_line_id', '=', tailoring_line_id),
                ('move_id.state', '=', 'posted'),
                ('move_id.move_type', '=', 'out_invoice')
            ], limit=1, order='id desc')
            
            target_inv_id = original_move_line.move_id.id if original_move_line else False
            
            if target_inv_id not in grouped_refunds:
                grouped_refunds[target_inv_id] = []
            grouped_refunds[target_inv_id].append(line_tuple)

        # Create one Credit Note per source invoice
        for inv_id, lines in grouped_refunds.items():
            self._create_move('out_refund', lines, original_invoice_id=inv_id)

    def _create_move(self, move_type, lines, original_invoice_id=False):
        vals = {
            'move_type': move_type,
            'partner_id': self.partner_id.id,
            'invoice_origin': self.name,
            'tailoring_order_id': self.id,
            'invoice_line_ids': lines,
        }

        if move_type == 'out_refund':
            # Use the specific ID passed from our new grouping function
            original_invoice = False
            if original_invoice_id:
                original_invoice = self.env['account.move'].browse(original_invoice_id)
            else:
                # Fallback to latest if for some reason the line link is missing
                original_invoice = self.env['account.move'].search([
                    ('tailoring_order_id', '=', self.id),
                    ('move_type', '=', 'out_invoice'),
                    ('state', '=', 'posted')
                ], limit=1, order='id desc')

            if original_invoice:
                vals.update({
                    'reversed_entry_id': original_invoice.id,
                    'ref': f"Refund for {original_invoice.name}",
                    'reason': _("Adjustment: Item removed or price change"),
                    'l10n_sa_reason': '3', # ZATCA Reason Code
                })
        
        return self.env['account.move'].create(vals)
# --- KEEPING YOUR EXISTING LINE AND ADDON MODELS ---
class TailoringOrderLine(models.Model):
    _name = 'tailoring.order.line'
    _description = 'Order Line'

    order_id = fields.Many2one('tailoring.order', ondelete='cascade')
    # Use Monetary for price fields to handle currencies correctly
    currency_id = fields.Many2one('res.currency', related='order_id.currency_id')
    
    product_id = fields.Many2one('product.product', string="Garment", required=True, domain=[('is_tailoring', '=', True)])
    garment_type_id = fields.Many2one('tailoring.garment.type', related='product_id.garment_type_id', store=True)
    is_bundle = fields.Boolean(related='product_id.is_bundle', string="Is Bundle")
    
    customer_measurement_id = fields.Many2one('tailoring.customer.measurement', string="Meas. Profile",
        domain="[('partner_id', '=', parent.partner_id), ('garment_type_id', '=', garment_type_id)]")
    measurement_summary = fields.Text("Workshop Details")
    
    fabric_product_id = fields.Many2one('product.product', string="Fabric Template")
    fabric_image = fields.Binary("Fabric Image")
    fabric_name = fields.Char("Fabric Name/Code")

    production_state = fields.Selection([
        ('draft', 'Draft'), 
        ('factory', 'In Factory'), 
        ('fitting', 'Trial Fitting'), 
        ('approved', 'Approved')
    ], default='draft', string="Status")
    
    trial_adjustment_notes = fields.Text("Fitting Notes")
    date_trial = fields.Date("Trial Date")
    delivery_date = fields.Date(string="Delivery Date")
    is_delivered = fields.Boolean(string="Delivered", default=False)
    addon_line_ids = fields.One2many('tailoring.order.line.addon', 'order_line_id', string="Addons")
    qty = fields.Float("Qty", default=1.0)
    price_unit = fields.Float("Base Price")
    price_subtotal = fields.Float(compute="_compute_subtotal", store=True)
    amt_invoiced = fields.Float("Amt Billed", readonly=True, copy=False)

    parent_line_id = fields.Many2one('tailoring.order.line', ondelete='cascade')
    child_line_ids = fields.One2many('tailoring.order.line', 'parent_line_id')
    tax_id = fields.Many2many('account.tax', string="Taxes", domain=[('type_tax_use', '=', 'sale')])
    price_tax = fields.Monetary(compute='_compute_subtotal', string="Tax Amount", store=True)
    price_total = fields.Monetary(compute='_compute_subtotal', string="Total with VAT", store=True)

    @api.onchange('customer_measurement_id')
    def _onchange_measurement_profile(self):
        if self.customer_measurement_id:
            lines = self.customer_measurement_id.measurement_line_ids
            summary = [f"{l.metric_id.name}: {l.value}" for l in lines]
            if self.customer_measurement_id.notes:
                summary.append(f"Notes: {self.customer_measurement_id.notes}")
            self.measurement_summary = "\n".join(summary)
            if self.production_state == 'draft':
                self.production_state = 'approved'

    @api.onchange('fabric_product_id')
    def _onchange_fabric_product_id(self):
        if self.fabric_product_id:
            self.fabric_image = self.fabric_product_id.image_1920
            self.fabric_name = self.fabric_product_id.name

    @api.depends('price_unit', 'qty', 'addon_line_ids.price_total', 'tax_id')
    def _compute_subtotal(self):
        for line in self:
            addon_sum = sum(line.addon_line_ids.mapped('price_total'))
            base_amount = (line.qty * line.price_unit) + addon_sum
        
        # Calculate Taxes
            taxes = line.tax_id.compute_all(base_amount, line.order_id.currency_id, line.qty, product=line.product_id)

            line.price_subtotal = taxes['total_excluded']
            line.price_tax = taxes['total_included'] - taxes['total_excluded']
            line.price_total = taxes['total_included']

    def action_unlink_line(self):
        for rec in self:
            if rec.production_state == 'factory':
                raise UserError(_("This item is already in the Factory. The Master has been paid and it cannot be returned or removed."))
        return self.unlink()

    def action_send_to_factory(self):
        for rec in self:
            rec.production_state = 'factory'

    def action_approve_fitting(self):
        for rec in self:
            if rec.production_state == 'fitting':
                rec.production_state = 'approved'

    def action_explode_bundle(self):
        self.ensure_one()
        if not self.order_id.id:
            raise UserError(_("Please Save the Order before exploding."))
        for component in self.product_id.constituent_ids:
            self.env['tailoring.order.line'].create({
                'order_id': self.order_id.id,
                'product_id': component.id,
                'parent_line_id': self.id,
                'price_unit': 0.0,
                'fabric_product_id': self.fabric_product_id.id,
                'customer_measurement_id': self.customer_measurement_id.id,
                'measurement_summary': self.measurement_summary,
            })
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_split_lines(self):
        self.ensure_one()
        if self.qty <= 1: return
        for i in range(int(self.qty) - 1):
            new_line = self.copy({'qty': 1.0, 'production_state': 'draft'})
            for addon in self.addon_line_ids:
                addon.copy({'order_line_id': new_line.id})
        self.qty = 1.0

    def action_show_addons(self):
        self.ensure_one()
        return {
            'name': _('Addons & Details'),
            'type': 'ir.actions.act_window',
            'res_model': 'tailoring.order.line',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'view_id': self.env.ref('tailoring_trading.view_tailoring_order_line_addon_form').id,
        }

class TailoringOrderLineAddon(models.Model):
    _name = 'tailoring.order.line.addon'
    _description = 'Order Line Addon'

    order_line_id = fields.Many2one('tailoring.order.line', ondelete='cascade')
    garment_type_id = fields.Many2one('tailoring.garment.type', related='order_line_id.garment_type_id', store=True)
    product_id = fields.Many2one('product.product', string="Addon", required=True,
        domain="[('is_addon', '=', True), ('garment_type_id', '=', garment_type_id)]")
    qty = fields.Float("Qty", default=1.0)
    price_unit = fields.Float("Unit Price")
    price_total = fields.Float(compute="_compute_total", store=True)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.price_unit = self.product_id.lst_price

    @api.depends('qty', 'price_unit')
    def _compute_total(self):
        for rec in self:
            rec.price_total = rec.qty * rec.price_unit

# --- Partner & Measurement Models Stay Exactly as they were ---
class ResPartner(models.Model):
    _inherit = 'res.partner'
    tailoring_measurement_ids = fields.One2many('tailoring.customer.measurement', 'partner_id', string="Measurements")
    tailoring_order_count = fields.Integer(compute='_compute_tailoring_order_count')

    def _compute_tailoring_order_count(self):
        for p in self:
            p.tailoring_order_count = self.env['tailoring.order'].search_count([('partner_id', 'child_of', p.id)])

    def action_view_tailoring_orders(self):
        self.ensure_one()
        return {
            'name': _('Tailoring Orders'),
            'type': 'ir.actions.act_window',
            'res_model': 'tailoring.order',
            'view_mode': 'list,form',
            'domain': [('partner_id', 'child_of', self.id)],
            'context': {'default_partner_id': self.id},
        }

class TailoringCustomerMeasurement(models.Model):
    _name = 'tailoring.customer.measurement'
    _description = 'Measurement Profile'
    partner_id = fields.Many2one('res.partner', ondelete='cascade')
    garment_type_id = fields.Many2one('tailoring.garment.type', required=True)
    date = fields.Date(default=fields.Date.today)
    measurement_line_ids = fields.One2many('tailoring.customer.measurement.line', 'measurement_id')
    notes = fields.Text()

class TailoringCustomerMeasurementLine(models.Model):
    _name = 'tailoring.customer.measurement.line'
    _description = 'Measurement Line'
    measurement_id = fields.Many2one('tailoring.customer.measurement', ondelete='cascade')
    metric_id = fields.Many2one('tailoring.metric.definition', required=True)
    value = fields.Float("Value")

class AccountMove(models.Model):
    _inherit = 'account.move'
    tailoring_order_id = fields.Many2one('tailoring.order', string='Tailoring Order')

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'
    tailoring_line_id = fields.Many2one('tailoring.order.line', string='Tailoring Line Source')