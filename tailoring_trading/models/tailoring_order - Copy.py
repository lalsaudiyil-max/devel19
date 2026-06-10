from odoo import models, fields, api, _
from odoo.fields import Command
from odoo.exceptions import UserError

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

    @api.depends('line_ids.price_subtotal')
    def _compute_amounts(self):
        for order in self:
            order.amount_total = sum(order.line_ids.mapped('price_subtotal'))

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
                    total += inv.amount_untaxed
                else:
                    total -= inv.amount_untaxed
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
    def action_create_invoice(self):
        self.ensure_one()
        invoice_lines = []

        for line in self.line_ids.filtered(lambda l: not l.parent_line_id):
        # 1. Gather all addons from Parent + Children (Jacket/Trousers)
            all_addon_lines = line.addon_line_ids
            for child in line.child_line_ids:
                all_addon_lines |= child.addon_line_ids

        # 2. Calculate the "Current Total Value" of this Suit (Price + all Addons)
            addon_total = sum(all_addon_lines.mapped('price_total'))
            current_suit_total = (line.qty * line.price_unit) + addon_total

        # 3. Calculate "Already Billed" for THIS specific line
        # We look at the linked invoice lines (Posted or Draft)
            already_billed = sum(self.env['account.move.line'].search([
                ('tailoring_line_id', '=', line.id),
                ('move_id.state', 'in', ['posted', 'draft']),
                ('move_id.move_type', '=', 'out_invoice')
            ]).mapped('price_subtotal'))
        
        # Subtract any Credit Notes (Refunds)
            already_refunded = sum(self.env['account.move.line'].search([
                ('tailoring_line_id', '=', line.id),
                ('move_id.state', 'in', ['posted', 'draft']),
                ('move_id.move_type', '=', 'out_refund')
            ]).mapped('price_subtotal'))

            net_billed = already_billed - already_refunded
        
        # 4. Find the Difference (The Delta)
            amount_to_bill = current_suit_total - net_billed

        # 5. Only create a line if there is money left to bill (more than 0.01 SR)
            if amount_to_bill > 0.01:
                addon_names = all_addon_lines.mapped('product_id.name')
                description = line.product_id.display_name
                if addon_names:
                    description += f" (Inc. {', '.join(addon_names)})"
            
            # If this is a secondary invoice (like an Express Fee), mark it clearly
                if net_billed > 0:
                    description = f"Additional Charges for: {description}"

                invoice_lines.append((0, 0, {
                    'product_id': line.product_id.id,
                    'name': description,
                    'quantity': 1.0, # We bill the "balance" as a lump sum
                    'price_unit': amount_to_bill,
                    'tax_ids': [(6, 0, line.product_id.taxes_id.ids)],
                    'tailoring_line_id': line.id, # KEY: Link it so we don't bill it again!
                }))

        if not invoice_lines:
            raise UserError(_("Everything is already billed or there's nothing to bill."))

    # 6. Create the Invoice
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'invoice_origin': self.name,
            'tailoring_order_id': self.id,
            'invoice_line_ids': invoice_lines,
        })
    
        self._compute_amt_invoiced() # Update the total billed counter
        return self.action_view_invoices()

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