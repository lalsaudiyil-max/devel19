from odoo import models, fields, api
from odoo.http import request

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # Point directly back to our inherited core device log row
    source_device_log_id = fields.Many2one(
        'res.device.log', 
        string='Terminal Source Log', 
        readonly=True,
        help="The specific hardware footprint record verified during transaction entry."
    )

    @api.model_create_multi
    def create(self, vals_list):
        device_cookie = request and hasattr(request, 'httprequest') and request.httprequest.cookies.get('odoo_strict_device_fingerprint')
        
        if device_cookie:
            device_log = self.env['res.device.log'].sudo().search([
                ('strict_auth_token', '=', device_cookie)
            ], limit=1)
            if device_log:
                for vals in vals_list:
                    vals['source_device_log_id'] = device_log.id

        return super(SaleOrder, self).create(vals_list)


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    source_device_log_id = fields.Many2one(
        'res.device.log', 
        string='Terminal Source Log', 
        readonly=True
    )

    @api.model_create_multi
    def create(self, vals_list):
        device_cookie = request and hasattr(request, 'httprequest') and request.httprequest.cookies.get('odoo_strict_device_fingerprint')
        
        if device_cookie:
            device_log = self.env['res.device.log'].sudo().search([
                ('strict_auth_token', '=', device_cookie)
            ], limit=1)
            if device_log:
                for vals in vals_list:
                    vals['source_device_log_id'] = device_log.id

        return super(PurchaseOrder, self).create(vals_list)