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
    factory_id = fields.Many2one('res.partner', string="Factory", required=True)
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
    amt_invoiced = fields.Monetary(string='Amount Billed', compute='_compute_amt_invoiced', store=True, currency_field='currency_id')
    amount_untaxed = fields.Monetary(string='Untaxed Amount', compute='_compute_amounts', store=True)
    amount_tax = fields.Monetary(string='Taxes', compute='_compute_amounts', store=True)
    # Balance field to show the Delta on the UI
    balance_due = fields.Monetary(string='Balance Due', compute='_compute_amounts', store=True)
    invoice_journal_id = fields.Many2one(
        'account.journal', 
        string="Invoice Journal",
        required=True,
        # The domain ensures they only see journals for the current company 
        # that are also in their 'allowed' list
        domain="[('type', '=', 'sale'), ('company_id', '=', company_id), ('id', 'in', allowed_journal_ids)]"
    )

    # Technical field to fetch the current user's allowed journals
    allowed_journal_ids = fields.Many2many(
        'account.journal', 
        compute='_compute_allowed_journals'
    )
    company_id = fields.Many2one(
        'res.company', 
        string='Company', 
        required=True, 
        default=lambda self: self.env.company
    )

    @api.depends('company_id')
    def _compute_allowed_journals(self):
        for rec in self:
            # Pull the list from the user's profile
            rec.allowed_journal_ids = self.env.user.allowed_journal_ids

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
            o.purchase_order_count = self.env['purchase.order'].search_count([('order_line.tailoring_line_id.order_id', '=', o.id)])

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

    def action_view_purchase_orders(self):
        self.ensure_one()
    # Find the POs again to get their IDs
        pos = self.env['purchase.order'].search([
            ('order_line.tailoring_line_id.order_id', '=', self.id)
        ])
        return {
            'type': 'ir.actions.act_window',
            'name': 'Factory Purchase Orders',
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('id', 'in', pos.ids)],
            'context': {'create': False},
        }
# --- UPDATED CREATE INVOICE LOGIC ---
    def action_create_invoice(self):
        self.ensure_one()
        invoice_lines = []
        refund_lines = []

        for line in self.line_ids.filtered(lambda l: not l.parent_line_id):
            # --- YOUR ORIGINAL WORKING PRICE LOGIC ---
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

            if abs(amount_to_bill) < 0.01:
                continue
            current_addon_names = ", ".join(all_addon_lines.mapped('product_id.name'))
            
            if amount_to_bill > 0:
                display_name = f"Addons for {line.product_id.name}: {current_addon_names}" if current_addon_names else f""
            else:
                display_name = f"Credit: Removal/Adjustment of {line.product_id.name} addons"
            # 5. Prepare line values (Using your original 1.15 logic)
            line_vals = {
                'product_id': line.product_id.id,
                'name': display_name,
                'quantity': 1.0,
                'price_unit': abs(amount_to_bill),
                'tax_ids': [(6, 0, line.tax_id.ids)],
                'tailoring_line_id': line.id,
            }

            if amount_to_bill > 0:
                invoice_lines.append((0, 0, line_vals))
            else:
                refund_lines.append((0, 0, line_vals))

        # --- EXECUTION ---
        if invoice_lines:
            self._create_move('out_invoice', invoice_lines)
    
        if refund_lines:
            # New helper to find the source invoice for these specific refunds
            self._create_refunds_with_correct_source(refund_lines)

        if not invoice_lines and not refund_lines:
            raise UserError(_("No financial changes detected to bill or refund."))

        return self.action_view_invoices()

    def _create_refunds_with_correct_source(self, refund_lines):
        """Finds the source invoice for each refund line and groups them"""
        grouped_refunds = {}

        for line_tuple in refund_lines:
            line_vals = line_tuple[2]
            t_line_id = line_vals.get('tailoring_line_id')
            
            # Find the most recent POSTED invoice for THIS specific Suit
            src_line = self.env['account.move.line'].search([
                ('tailoring_line_id', '=', t_line_id),
                ('move_id.state', '=', 'posted'),
                ('move_id.move_type', '=', 'out_invoice')
            ], limit=1, order='id desc')
            
            inv_id = src_line.move_id.id if src_line else False
            
            if inv_id not in grouped_refunds:
                grouped_refunds[inv_id] = []
            grouped_refunds[inv_id].append(line_tuple)

        for inv_id, lines in grouped_refunds.items():
            self._create_move('out_refund', lines, original_invoice_id=inv_id)

    def _create_move(self, move_type, lines, original_invoice_id=False):
        vals = {
            'move_type': move_type,
            'partner_id': self.partner_id.id,
            'journal_id': self.invoice_journal_id.id,
            'invoice_origin': self.name,
            'tailoring_order_id': self.id,
            'invoice_line_ids': lines,
        }

        if move_type == 'out_refund':
            # Use the specific source found by the grouping helper
            if original_invoice_id:
                orig = self.env['account.move'].browse(original_invoice_id)
                vals.update({
                    'reversed_entry_id': orig.id,
                    'ref': f"Refund for {orig.name}",
                   # 'l10n_sa_reason': '[BR-KSA-17-reason-3] - Amendment of the supply value which is pre-agreed upon between the supplier and consumer',
                })
        return self.env['account.move'].create(vals)
# --- KEEPING YOUR EXISTING LINE AND ADDON MODELS ---
class TailoringOrderLine(models.Model):
    _name = 'tailoring.order.line'
    _description = 'Order Line'
    _order = 'sequence, id'

    sequence = fields.Integer(string="Sequence", default=10)
    order_id = fields.Many2one('tailoring.order', ondelete='cascade')
    # Use Monetary for price fields to handle currencies correctly
    currency_id = fields.Many2one('res.currency', related='order_id.currency_id')
    
    product_id = fields.Many2one('product.product', string="Product", required=True, domain=[('is_tailoring', '=', True),('is_addon', '=', False)])
    garment_type_id = fields.Many2one('tailoring.garment.type', related='product_id.garment_type_id', store=True)
    is_bundle = fields.Boolean(related='product_id.is_bundle', string="Is Bundle")
    
    customer_measurement_id = fields.Many2one('tailoring.customer.measurement', string="Meas. Profile",
        domain="[('partner_id', '=', parent.partner_id), ('garment_type_id', '=', garment_type_id)]")
    measurement_summary = fields.Text( string="Measurement Summary")
    factory_product_id = fields.Many2one('product.product', string="Factory Item")
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
            for child in self.child_line_ids:
                child.fabric_product_id = self.fabric_product_id

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if not self.product_id:
            return
            
        # If it's a child/component, keep price at 0. 
        # Otherwise, fetch the standard garment price.
        if self.parent_line_id:
            self.price_unit = 0.0
            self.tax_id = self.product_id.taxes_id
        else:
            self.price_unit = self.product_id.lst_price
            self.tax_id = self.product_id.taxes_id
           #self.action_explode_bundle()

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
              # Kill children then self
            if line.parent_line_id:
                raise UserError("You cannot delete individual components. Please delete the Parent Bundle (Suit) to remove")
            self.mapped('child_line_ids').unlink()
        return self.unlink()

    def action_send_to_factory(self):
        self.ensure_one()
        # 1. Validation: Must be Invoiced or Approved
        if not  self.production_state != 'Approved':
            raise UserError(_("Item must be Invoiced or Approved before sending to factory."))

        # 2. Get the Bulk PO
        factory = self.order_id.factory_id
        #factory = 13
        target_po = self.env['purchase.order'].search([
            ('partner_id', '=', factory.id),
            ('state', '=', 'draft')
        ], limit=1) or self.env['purchase.order'].create({'partner_id': factory.id, 'origin': 'Bulk Orders','date_planned': fields.Datetime.now(), })

        po_lines = []
        components_to_process = self.child_line_ids if self.child_line_ids else self
        # 3. Process each child component (Jacket, Trousers) separately
        for component in components_to_process:
            # 1. Gather Styles and Measurements for this specific component
            # (Assuming you have measurement_ids and style_ids on the line)
            #profile = self.env['tailoring.customer.measurement'].search(('partner_id', '=', self.order_id.partner_id.id),('garment_type_id', '=', component.garment_type_id.id)], limit=1, order='date desc')
            measurements=""
# 2. Build the summary string from the lines
            profile = self.env['tailoring.customer.measurement'].search([
                ('partner_id', '=', self.order_id.partner_id.id),
                ('garment_type_id', '=', component.garment_type_id.id)
            ], limit=1, order='date desc')

# 2. Build the summary string from the lines
            if profile:
                measurements = "\n".join([
                    f"{line.metric_id.name}: {line.value}" 
                    for line in profile.measurement_line_ids 
                    if line.value > 0
                ])
            else:
                measurements = ""            #style_details = "\n".join([f"- {s.attribute_id.name}: {s.name}" for s in component.style_ids])
            #measurements = "\n".join([f"- {m.metric_id}: {m.value}" for m in component.customer_measurement_id])
            
            # 2. Addons for this component
            comp_addons = component.addon_line_ids.mapped('product_id.name')
            
            # 3. Build the "Factory Master Sheet" Description
            # This is the 'name' field that will travel to the MO
            description = (
                f"ORDER: {self.order_id.name} | {self.product_id.name}\n"
                f"COMPONENT: {component.product_id.name}\n"
               # f"--- STYLE & DESIGN ---\n{style_details}\n"
                f"--- MEASUREMENTS ---\n{measurements}\n"
                f"--- ADDONS ---\n{', '.join(comp_addons) if comp_addons else 'Standard'}"
            )
            base_cost = component.product_id.standard_price or 0.0
            addons_cost = sum(addon.product_id.standard_price for addon in component.addon_line_ids if addon.product_id)
            factory_id = component.factory_product_id.id or component.product_id.product_tmpl_id.factory_product_id.id
            if not factory_id:
                raise UserError(f"No Factory Product linked for {component.product_id.name}. Please check the Product or Template settings.")
            po_line = self.env['purchase.order.line'].create({
                'order_id': target_po.id,
                'product_id': factory_id,
                'name': description,
                'product_qty': component.qty,
                'price_unit': base_cost + addons_cost,
                'date_planned': component.date_trial,
                'tailoring_line_id': component.id,
            })

    # B. Trigger the stock move logic (Fixes the "Stock Move" error)
            po_line.onchange_product_id()

    # C. Calculate your custom costs (Garment + Addons)
         #   base_cost = component.product_id.standard_price or 0.0
         #   addons_cost = sum(addon.product_id.standard_price for addon in component.addon_line_ids if addon.product_id)
    
    # D. Overwrite with your custom Tailoring info
            po_line.write({
                'name': description, # This carries the info to the MO
                'price_unit': base_cost + addons_cost,
                'date_planned': component.date_trial,
                'tailoring_line_id': component.id,
            })

            # Lock the component and its addons
            component.production_state = 'factory'
            #comp_addons.write({'production_state': 'factory'})

        # 5. Finalize the PO and the Main Suit line
        target_po.write({'order_line': po_lines})
        self.production_state =  'factory'
        
        return True

    def action_approve_fitting(self):
        for rec in self:
            if rec.production_state == 'fitting':
                rec.production_state = 'approved'

    def action_explode_bundle(self):
        self.ensure_one()
        if not self.order_id:
            raise UserError("Please save the order first.")
        existing_children = self.env['tailoring.order.line'].search([
            ('parent_line_id', '=', self.id)
        ])
        if existing_children:
            return True 
    # 1. Prevent double-explosion
    # 2. Get the base sequence
        base_seq = self.sequence

    # 3. Create children with a +1 increment
    # Since we use 10-20-30 for parents, +1, +2, +3 fits perfectly inside the gap
        for idx, component in enumerate(self.product_id.constituent_ids, start=1):
        # Determine the Factory Product Mapping
            f_product = component.factory_product_id.id or component.id
        
            self.env['tailoring.order.line'].create({
                'order_id': self.order_id.id,
                'product_id': component.id,
                'factory_product_id': f_product,
                'parent_line_id': self.id,
                'sequence': base_seq + idx, # Results in 11, 12, 13...
                'price_unit': 0.0,
                'measurement_summary': self.measurement_summary,
                'fabric_product_id': self.fabric_product_id.id,
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

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    # Adding 'groups' or removing private restrictions
    commission_rate = fields.Float(
        string="Commission Rate", 
        groups="base.group_user" # This makes it readable by any logged-in staff
    )

class HrEmployeePublic(models.Model):
    _inherit = 'hr.employee.public'

    # This tells Odoo to also allow this field in the public context
    commission_rate = fields.Float(readonly=True)
