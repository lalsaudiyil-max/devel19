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
        }

class TailoringOrderLine(models.Model):
    _name = 'tailoring.order.line'
    _description = 'Order Line'

    order_id = fields.Many2one('tailoring.order', ondelete='cascade')
    product_id = fields.Many2one('product.product', string="Garment", required=True, domain=[('is_tailoring', '=', True)])
    garment_type_id = fields.Many2one('tailoring.garment.type', related='product_id.garment_type_id', store=True)
    is_bundle = fields.Boolean(related='product_id.is_bundle', string="Is Bundle")
    
    # Measurement Logic
    customer_measurement_id = fields.Many2one('tailoring.customer.measurement', string="Meas. Profile",
        domain="[('partner_id', '=', parent.partner_id), ('garment_type_id', '=', garment_type_id)]")
    measurement_summary = fields.Text("Workshop Details")
    
    # Fabric Logic (Odoo 19)
    fabric_product_id = fields.Many2one('product.product', string="Fabric Template",
        domain="['|', ('uom_id.name', '=', 'm'), ('uom_id.relative_uom_id.name', '=', 'm')]")
    fabric_image = fields.Binary("Fabric Image")
    fabric_name = fields.Char("Fabric Name/Code")

    # Bundle logic
    parent_line_id = fields.Many2one('tailoring.order.line', ondelete='cascade')
    child_line_ids = fields.One2many('tailoring.order.line', 'parent_line_id')
    
    # Production Tracking
    production_state = fields.Selection([
        ('draft', 'Draft'), 
        ('factory', 'In Factory'), 
        ('fitting', 'Trial Fitting'), 
        ('approved', 'Approved')
    ], default='draft', string="Status")
    
    trial_adjustment_notes = fields.Text("Fitting Notes")
    date_trial = fields.Date("Trial Date")
    
    # Addons & Financials
    addon_line_ids = fields.One2many('tailoring.order.line.addon', 'order_line_id', string="Addons")
    qty = fields.Float("Qty", default=1.0)
    price_unit = fields.Float("Base Price")
    price_subtotal = fields.Float(compute="_compute_subtotal", store=True)
    amt_invoiced = fields.Float("Amt Billed", readonly=True, copy=False)

    @api.onchange('customer_measurement_id')
    def _onchange_measurement_profile(self):
        if self.customer_measurement_id:
            lines = self.customer_measurement_id.measurement_line_ids
            summary = [f"{l.metric_id.name}: {l.value}" for l in lines]
            if self.customer_measurement_id.notes:
                summary.append(f"Notes: {self.customer_measurement_id.notes}")
            self.measurement_summary = "\n".join(summary)

    @api.onchange('fabric_product_id')
    def _onchange_fabric_product_id(self):
        if self.fabric_product_id:
            self.fabric_image = self.fabric_product_id.image_1920
            self.fabric_name = self.fabric_product_id.name

    @api.depends('price_unit', 'qty', 'addon_line_ids.price_total')
    def _compute_subtotal(self):
        for line in self:
            addon_sum = sum(line.addon_line_ids.mapped('price_total'))
            line.price_subtotal = (line.qty * line.price_unit) + addon_sum

    def action_explode_bundle(self):
        self.ensure_one()
        if not self.order_id.id:
            raise UserError(_("Please Save the Order before exploding."))
        if self.child_line_ids:
            return
        for component in self.product_id.constituent_ids:
            self.env['tailoring.order.line'].create({
                'order_id': self.order_id.id,
                'product_id': component.id,
                'parent_line_id': self.id,
                'price_unit': 0.0,
                'fabric_product_id': self.fabric_product_id.id,
                'fabric_image': self.fabric_image,
                'customer_measurement_id': self.customer_measurement_id.id,
                'measurement_summary': self.measurement_summary,
            })
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_split_lines(self):
        self.ensure_one()
        if self.qty <= 1:
            return
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
            # Replace with your actual addon form view ID
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

# --- Measurement Models ---

class ResPartner(models.Model):
    _inherit = 'res.partner'

    tailoring_measurement_ids = fields.One2many('tailoring.customer.measurement', 'partner_id', string="Measurements")
    tailoring_order_count = fields.Integer(compute='_compute_tailoring_order_count')

    def _compute_tailoring_order_count(self):
        for p in self:
            # Search for orders linked to this partner or its children (contacts)
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

class TailoringOrder(models.Model):
    _inherit = 'tailoring.order'

    def action_create_invoice(self):
        """Creates a ZATCA-ready draft invoice for all approved or factory-sent lines."""
        self.ensure_one()
        invoiceable_lines = self.line_ids.filtered(lambda l: l.production_state != 'draft' and l.amt_invoiced == 0)
        
        if not invoiceable_lines:
            raise UserError(_("No lines are ready for invoicing. Move items to 'Factory' or 'Approved' status first."))

        invoice_vals = {
            'move_type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'invoice_origin': self.name,
            'invoice_line_ids': [],
        }

        for line in invoiceable_lines:
            # Main Garment Line
            invoice_vals['invoice_line_ids'].append(Command.create({
                'product_id': line.product_id.id,
                'quantity': line.qty,
                'price_unit': line.price_unit,
                'name': f"{line.product_id.name} (Ref: {self.name})",
            }))
            # Addon Lines
            for addon in line.addon_line_ids:
                invoice_vals['invoice_line_ids'].append(Command.create({
                    'product_id': addon.product_id.id,
                    'quantity': addon.qty,
                    'price_unit': addon.price_unit,
                    'name': f"   + {addon.product_id.name}",
                }))
            
            # Mark as invoiced to prevent double billing
            line.amt_invoiced = line.price_subtotal

        new_invoice = self.env['account.move'].create(invoice_vals)
        return self.action_view_invoices()

class TailoringOrderLine(models.Model):
    _inherit = 'tailoring.order.line'

    def action_approve_fitting(self):
        """Moves line from Trial Fitting to Approved and records notes."""
        for rec in self:
            if rec.production_state == 'fitting':
                rec.production_state = 'approved'
                rec.order_id.message_post(body=f"✅ Garment {rec.product_id.name} approved after trial.")

    def action_send_to_factory(self):
        for rec in self:
            rec.production_state = 'factory'