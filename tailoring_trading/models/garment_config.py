from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = 'product.template'
    
    is_tailoring = fields.Boolean("Is Tailoring")
    is_addon = fields.Boolean("Is Addon")
    is_bundle = fields.Boolean("Is Bundle (Suit)")
    garment_type_id = fields.Many2one('tailoring.garment.type', string="Garment Type")
    min_price = fields.Float("Minimum Allowed Price")
    # Explicitly defining the relation table and columns to avoid schema mismatch
    constituent_ids = fields.Many2many('product.product', 'tailoring_product_bundle_rel', 
                                       'template_id', 'product_id', string="Bundle Components")
    factory_product_id = fields.Many2one(
        'product.product', 
        string="Factory Production Item",
#        domain=[('type', '=ilike', 'consu')], # Must be a Storable product for the MO
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

class TailoringGarmentType(models.Model):
    _name = 'tailoring.garment.type'
    _description = 'Garment Type'
    name = fields.Char("Type Name", required=True)
    metric_ids = fields.One2many('tailoring.metric.definition', 'garment_type_id', string="Measurements")
    spec_ids = fields.One2many('tailoring.spec.definition', 'garment_type_id', string="Design Features")

class TailoringMetricDefinition(models.Model):
    _name = 'tailoring.metric.definition'
    _description = 'Tailoring Metric Definition'
    name = fields.Char("Metric")
    garment_type_id = fields.Many2one('tailoring.garment.type')

class TailoringSpecDefinition(models.Model):
    _name = 'tailoring.spec.definition'
    _description = 'Tailoring Spec Definition'
    name = fields.Char("Feature")
    garment_type_id = fields.Many2one('tailoring.garment.type')
    value_ids = fields.One2many('tailoring.spec.value', 'spec_id')

class TailoringSpecValue(models.Model):
    _name = 'tailoring.spec.value'
    _description = 'Tailoring Spec Value'
    name = fields.Char("Value")
    spec_id = fields.Many2one('tailoring.spec.definition')
