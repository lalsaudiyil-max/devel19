# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.tools.float_utils import float_compare, float_repr
import logging

_logger = logging.getLogger(__name__)


# ============================================================
# POS ORDER LINE
# ============================================================

    
class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    line_salesman_id = fields.Many2one(
        'hr.employee',
        string='Salesman'
    )
    
    def _load_pos_data_fields(self, config_id):
        """
        Make salesman field available to POS frontend
        """
        fields_list = super()._load_pos_data_fields(config_id)
        if 'line_salesman_id' not in fields_list:
            fields_list.append('line_salesman_id')
       
        return fields_list

# ============================================================
# HR EMPLOYEE
# ============================================================

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    cashier_discount_limit = fields.Float()
    
    def _load_pos_data_fields(self, config_id):
        """
        Make salesman field available to POS frontend
        """
        fields_list = super()._load_pos_data_fields(config_id)
        if 'cashier_discount_limit' not in fields_list:
            fields_list.append('cashier_discount_limit')
       
        return fields_list
# ============================================================
# POS ORDER
# ============================================================
class PosOrder(models.Model):
    _inherit = 'pos.order'

    
    def _prepare_invoice_lines(self, move_type):
        """
        Prepare invoice lines from POS order lines
        with strengthened tax fallback and salesman propagation.
        """
        invoice_lines = []

        for order in self:
            line_values_list = order.with_context(
                invoicing=True
            )._prepare_tax_base_line_values()

            for line_values in line_values_list:
                line = line_values['record']
                vals = order._get_invoice_lines_values(
                    line_values, line, move_type
                )

                # ------------------------------------------------
                # TAX SAFETY (POS → PRODUCT → EMERGENCY FALLBACK)
                # ------------------------------------------------
                taxes = line.tax_ids

                if not taxes:
                    taxes = line.product_id.taxes_id.filtered(
                        lambda t: t.company_id == order.company_id
                    )

                if not taxes:
                    taxes = self.env['account.tax'].search([
                        ('type_tax_use', '=', 'sale'),
                        ('company_id', '=', order.company_id.id)
                    ], limit=1)

                if taxes:
                    vals['tax_ids'] = [(6, 0, taxes.ids)]
                # ------------------------------------------------

                # Salesman propagation
                if line.line_salesman_id:
                    vals['line_salesman_id'] = line.line_salesman_id.id

                invoice_lines.append((0, 0, vals))

                # ------------------------------------------------
                # DISCOUNT NOTE (Percentage Pricelist)
                # ------------------------------------------------
                is_percentage = order.pricelist_id and any(
                    order.pricelist_id.item_ids.filtered(
                        lambda r: r.compute_price == "percentage"
                    )
                )

                if (
                    is_percentage
                    and float_compare(
                        line.price_unit,
                        line.product_id.lst_price,
                        precision_rounding=order.currency_id.rounding
                    ) < 0
                ):
                    invoice_lines.append((0, 0, {
                        'name': _(
                            'Price discount from %(original)s to %(discounted)s',
                            original=float_repr(
                                line.product_id.lst_price,
                                order.currency_id.decimal_places
                            ),
                            discounted=float_repr(
                                line.price_unit,
                                order.currency_id.decimal_places
                            ),
                        ),
                        'display_type': 'line_note',
                    }))
                # ------------------------------------------------

                if line.customer_note:
                    invoice_lines.append((0, 0, {
                        'name': line.customer_note,
                        'display_type': 'line_note',
                    }))

            if order.general_customer_note:
                invoice_lines.append((0, 0, {
                    'name': order.general_customer_note,
                    'display_type': 'line_note',
                }))

        return invoice_lines


# ============================================================
# ACCOUNT MOVE LINE (INVOICE)
# ============================================================
class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    line_salesman_id = fields.Many2one(
        'hr.employee',
        string='Salesman'
    )



class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.model
    def _get_allowed_pos_template_ids(self, config):
        location_id = config.picking_type_id.default_location_src_id.id
        if not location_id:
            return []

        query = """
            SELECT DISTINCT pt.id
            FROM product_template pt
            LEFT JOIN product_product pp ON pp.product_tmpl_id = pt.id
            LEFT JOIN stock_quant sq ON sq.product_id = pp.id
            WHERE
                pt.type = 'service'
                OR (
                    pt.type = 'consu'
                    AND sq.location_id = %s
                    AND sq.quantity > 0
                )
        """

        self.env.cr.execute(query, (location_id,))
        rows = self.env.cr.fetchall()

        return [r[0] for r in rows]

    @api.model
    def _load_pos_data_domain(self, data, config):
        domain = super()._load_pos_data_domain(data, config)

        allowed_ids = self._get_allowed_pos_template_ids(config)

        if allowed_ids:
            domain = domain + [('id', 'in', allowed_ids)]

        return domain

class ProductProduct(models.Model):
    _inherit = 'product.product'

    discount_limit = fields.Float()

    @api.model
    def _get_allowed_pos_history_ids(self, config):
        location_id = config.picking_type_id.default_location_src_id.id
        if not location_id:
            return []
            
        query = """
            SELECT DISTINCT pp.id 
            FROM product_product pp
            JOIN product_template pt ON pp.product_tmpl_id = pt.id
            LEFT JOIN stock_move_line sml ON sml.product_id = pp.id 
                AND sml.location_dest_id = %s 
                AND sml.state = 'done'
            WHERE pt.type = 'service' 
               OR sml.id IS NOT NULL
        """
        self.env.cr.execute(query, (location_id,))
        return [row[0] for row in self.env.cr.fetchall()]

    def _load_pos_data_fields(self, config_id):
        """
        Make x_studio_discount_limit field available to POS frontend
        """
        fields_list = super()._load_pos_data_fields(config_id)
        if 'discount_limit' not in fields_list:
            fields_list.append('discount_limit')
        return fields_list

    @api.model
    def _load_pos_data_domain(self, data, config):
        domain = super()._load_pos_data_domain(data, config)
        
            
        return domain
