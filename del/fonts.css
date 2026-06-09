from odoo import models, fields, api
from odoo.exceptions import AccessError
from odoo.exceptions import UserError


# =========================================================
# Warehouse Branding
# =========================================================
class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    branch_name = fields.Char("Branch Name (EN)")
    branch_name_ar = fields.Char("Branch Name (AR)")
    branch_address = fields.Text("Address (EN)")
    branch_address_ar = fields.Text("Address (AR)")
    
    branch_logo = fields.Binary("Logo")
    branch_logo_ar = fields.Binary("Logo (AR)")
    branch_header_en = fields.Binary("Header (EN)")
    branch_header_ar = fields.Binary("Header (AR)")
    branch_footer_en = fields.Binary("Footer (EN)")
    branch_footer_ar = fields.Binary("Footer (AR)")


# =========================================================
# Account Journal Extensions
# =========================================================
class AccountJournal(models.Model):
    _inherit = 'account.journal'

    warehouse_id = fields.Many2one('stock.warehouse', string="Linked Warehouse")
    x_analytic_account_id = fields.Many2one('account.analytic.account',string="Analytic Account")
    x_customer_tag_ids = fields.Many2many('res.partner.category',string="Contact Tags")
    x_payment_method_ids = fields.Many2many('account.payment.method',string="Payment Method")
    x_default_sales_pricelist_id = fields.Many2one('product.pricelist',string="Default Pricelist")
    x_not_available_pricelist_ids = fields.Many2many('product.pricelist', string="Not Available Pricelist")
    x_team_id = fields.Many2one('crm.team', string="Sales Team")

    x_available_pricelist_ids = fields.Many2many(
        'product.pricelist',
        compute='_compute_available_pricelists',
        store=False, string="Available Pricelist"
    )

    @api.depends('x_not_available_pricelist_ids')
    def _compute_available_pricelists(self):
        for journal in self:
            all_pl = self.env['product.pricelist'].search([
                ('company_id', '=', journal.company_id.id)
            ])
            journal.x_available_pricelist_ids = all_pl - journal.x_not_available_pricelist_ids


# =========================================================
# User Extensions
# =========================================================
class ResUsers(models.Model):
    _inherit = 'res.users'

    allowed_journal_ids = fields.Many2many(
        'account.journal',
        'res_users_sales_journal_rel',
        'user_id', 'journal_id',
        string="Allowed Sales Journals"
    )

    allowed_pay_journal_ids = fields.Many2many(
        'account.journal',
        'res_users_payment_journal_rel',
        'user_id', 'journal_id',
        string="Allowed Payment Journals"
    )

    x_default_sales_journal_id = fields.Many2one(
        'account.journal',
        domain="[('id', 'in', allowed_journal_ids)]",
        string="Default Sales Journal"
    )

    x_default_sales_team_id = fields.Many2one('crm.team',string="Default Sales Team")


# =========================================================
# Invoice Branding Helper
# =========================================================
class AccountMove(models.Model):
    _inherit = 'account.move'

    def get_warehouse_branding(self):
        self.ensure_one()
        return self.journal_id.warehouse_id if self.journal_id else False


# =========================================================
# Payment Restrictions
# =========================================================
class AccountPayment(models.Model):
    _inherit = 'account.payment'

    @api.depends('company_id', 'payment_type', 'partner_type')
    def _compute_available_journal_ids(self):
        super()._compute_available_journal_ids()
        user = self.env.user

        if not user.allowed_pay_journal_ids:
            return

        for payment in self:
            payment.available_journal_ids = user.allowed_pay_journal_ids


# =========================================================
# Partner Logic
# =========================================================


class ResPartner(models.Model):
    _inherit = 'res.partner'


    # --------------------------------------------------
    # DEFAULT VALUES
    # --------------------------------------------------
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        user = self.env.user

        # Only enforce for limited users (those having allowed journals)
        if user.allowed_journal_ids:

            # Always create as customer
            if 'customer_rank' in fields_list:
                res.setdefault('customer_rank', 1)

            # Get allowed pricelists from journals
            allowed_pricelists = user.allowed_journal_ids.mapped(
                'x_available_pricelist_ids'
            )
            default_pricelist = user.allowed_journal_ids.mapped(
                'x_default_sales_pricelist_id'
            )

            # Set default pricelist if not already set
            if 'property_product_pricelist' in fields_list and not res.get('property_product_pricelist'):
                if default_pricelist:
                    res['property_product_pricelist'] = default_pricelist
                elif user.partner_id.property_product_pricelist:
                    res['property_product_pricelist'] = user.partner_id.property_product_pricelist.id

            # Default customer tags from journals
            if 'category_id' in fields_list:
                allowed_tags = user.allowed_journal_ids.mapped('x_customer_tag_ids')
                if allowed_tags:
                    res['category_id'] = [(4, tag.id) for tag in allowed_tags]

        return res

    # --------------------------------------------------
    # CREATE ENFORCEMENT
    # --------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        user = self.env.user

        for vals in vals_list:

            if user.allowed_journal_ids:

                # Ensure customer
                vals.setdefault('customer_rank', 1)

                # Enforce allowed pricelist
                default_pricelist = user.allowed_journal_ids.mapped(
                    'x_default_sales_pricelist_id'
                )

                if not vals.get('property_product_pricelist'):
                    if default_pricelist:
                        vals['property_product_pricelist'] = default_pricelist
                    elif user.partner_id.property_product_pricelist:
                        vals['property_product_pricelist'] = user.partner_id.property_product_pricelist.id

        partners = super().create(vals_list)

        # Assign tags after creation
        if user.allowed_journal_ids:
            allowed_tags = user.allowed_journal_ids.mapped('x_customer_tag_ids')
            if allowed_tags:
                for partner in partners:
                    partner.category_id = [(4, tag.id) for tag in allowed_tags]

        return partners
        return res


# =========================================================
# Sale Order Defaults (context-based, correct)
# =========================================================
class SaleOrder(models.Model):
    _inherit = 'sale.order'


    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        user = self.env.user

        if 'team_id' in fields_list and user.x_default_sales_team_id:
            res['team_id'] = user.x_default_sales_team_id.id

        if user.x_default_sales_journal_id:
            self = self.with_context(
                default_invoice_journal_id=user.x_default_sales_journal_id.id
            )

        if 'pricelist_id' in fields_list:
            journal_id = user.x_default_sales_journal_id.id
            if journal_id:
                journal = self.env['account.journal'].browse(journal_id)
                if journal.x_default_sales_pricelist_id:
                    res['pricelist_id'] = journal.x_default_sales_pricelist_id.id
            elif user.partner_id.property_product_pricelist:
                res['pricelist_id'] = user.partner_id.property_product_pricelist.id

        return res
