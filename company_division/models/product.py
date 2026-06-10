from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    division_id = fields.Many2one('company.division', string='Division')
    internal_quality = fields.Char(string='Internal Quality')


