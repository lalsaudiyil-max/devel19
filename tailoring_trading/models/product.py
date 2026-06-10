from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_tailoring = fields.Boolean("Is Tailoring Service", default=False)
    garment_type_id = fields.Many2one('tailoring.garment.type', string="Garment Type")
    min_price = fields.Float("Minimum Allowed Price")
    is_bundle = fields.Boolean("Is a Bundle (e.g. 2PC Suit)")
    constituent_ids = fields.Many2many(
        'product.product', 'product_bundle_rel', 'src_id', 'dest_id',
        string="Bundle Components"
    )
    factory_product_id = fields.Many2one(
        'product.product', 
        string="Factory Production Item",
        domain=[('type', '=', 'product')], # Must be a Storable product for the MO
        help="The physical product used by the factory for this service."
    )
class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'
    
    # Link to the original tailoring line for tracking
    tailoring_line_id = fields.Many2one('tailoring.order.line', string="Tailoring Line Ref")

class MrpProduction(models.Model):
    _inherit = 'mrp.production'
    
    # The MO carries the ID to update status back to Trading
    tailoring_line_id = fields.Many2one('tailoring.order.line', string="Tailoring Line Ref")