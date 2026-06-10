from odoo import models, fields, api

class ProductTemplate(models.Model):
    _inherit = "product.template"

    qty_invoiced = fields.Float(
        string="Qty Invoiced",
        compute="_compute_qty_invoiced",
        help="Total quantity invoiced to customers"
    )

    qty_billed = fields.Float(
        string="Qty Billed",
        compute="_compute_qty_billed",
        help="Total quantity received from vendor bills"
    )

    def _compute_qty_invoiced(self):
        for product in self:
            domain = [
                ('move_id.move_type', '=', 'out_invoice'),
                ('move_id.state', '=', 'posted'),
                ('product_id.product_tmpl_id', '=', product.id)
            ]
            result = self.env['account.move.line'].read_group(
                domain=domain,
                fields=['quantity:sum'],
                groupby=[]
            )
            product.qty_invoiced = result[0]['quantity'] if result else 0.0

    def _compute_qty_billed(self):
        for product in self:
            domain = [
                ('move_id.move_type', '=', 'in_invoice'),
                ('move_id.state', '=', 'posted'),
                ('product_id.product_tmpl_id', '=', product.id)
            ]
            result = self.env['account.move.line'].read_group(
                domain=domain,
                fields=['quantity:sum'],
                groupby=[]
            )
            product.qty_billed = result[0]['quantity'] if result else 0.0

    # Action to open invoices (opens account.move, filtered)
    def action_view_invoices(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Invoices',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted'),
                ('invoice_line_ids.product_id.product_tmpl_id', '=', self.id)
            ],
        }

    # Action to open bills (opens account.move, filtered)
    def action_view_bills(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Vendor Bills',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [
                ('move_type', '=', 'in_invoice'),
                ('state', '=', 'posted'),
                ('invoice_line_ids.product_id.product_tmpl_id', '=', self.id)
            ],
        }

class ProductProduct(models.Model):
    _inherit = "product.product"

    qty_invoiced = fields.Float(
        string="Qty Invoiced",
        compute="_compute_qty_invoiced",
        help="Total quantity invoiced for this variant"
    )
    qty_billed = fields.Float(
        string="Qty Billed",
        compute="_compute_qty_billed",
        help="Total quantity billed for this variant"
    )

    def _compute_qty_invoiced(self):
        for product in self:
            domain = [
                ('move_id.move_type', '=', 'out_invoice'),
                ('move_id.state', '=', 'posted'),
                ('product_id', '=', product.id)
            ]
            result = self.env['account.move.line'].read_group(
                domain=domain,
                fields=['quantity:sum'],
                groupby=[]
            )
            product.qty_invoiced = result[0]['quantity'] if result else 0.0

    def _compute_qty_billed(self):
        for product in self:
            domain = [
                ('move_id.move_type', '=', 'in_invoice'),
                ('move_id.state', '=', 'posted'),
                ('product_id', '=', product.id)
            ]
            result = self.env['account.move.line'].read_group(
                domain=domain,
                fields=['quantity:sum'],
                groupby=[]
            )
            product.qty_billed = result[0]['quantity'] if result else 0.0

    def action_view_invoices(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Invoices',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted'),
                ('invoice_line_ids.product_id', '=', self.id)
            ],
        }

    def action_view_bills(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Vendor Bills',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [
                ('move_type', '=', 'in_invoice'),
                ('state', '=', 'posted'),
                ('invoice_line_ids.product_id', '=', self.id)
            ],
        }