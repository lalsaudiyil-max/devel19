from odoo import models, api
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        user = self.env.user

        if user.allowed_journal_ids:
            journal = user.allowed_journal_ids[0]
            res['journal_id'] = user.x_default_sales_journal_id.id
            if journal.warehouse_id:
                res['warehouse_id'] = journal.warehouse_id.id

        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('journal_id'):
                journal = self.env['account.journal'].browse(vals['journal_id'])
                if journal.warehouse_id:
                    vals['warehouse_id'] = journal.warehouse_id.id

        return super().create(vals_list)

    @api.onchange('journal_id')
    def _onchange_journal_update_warehouse(self):
        if self.journal_id and self.journal_id.warehouse_id:
            self.warehouse_id = self.journal_id.warehouse_id

    @api.onchange('partner_id')
    def _onchange_partner_keep_warehouse(self):
        # Run Odoo standard partner logic first
        super()._onchange_partner_id()

        # Re-apply warehouse from journal
        if self.journal_id and self.journal_id.warehouse_id:
            self.warehouse_id = self.journal_id.warehouse_id
  

class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    @api.depends('company_id', 'payment_type', 'partner_type', 'journal_id')
    def _compute_available_journal_ids(self):
        super()._compute_available_journal_ids()
        user = self.env.user
        if not user.allowed_pay_journal_ids:
            return

        for payment in self:
            # intersect Odoo's computed journals with allowed journals
            payment.available_journal_ids =  user.allowed_pay_journal_ids

