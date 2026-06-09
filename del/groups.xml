from odoo import models, fields, api, _

class ProductImageRequest(models.Model):
    _name = 'product.image.request'
    _description = 'Product Image Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    product_id = fields.Many2one('product.product', string="Product", required=True, tracking=True)
    product_barcode = fields.Char(related='product_id.barcode', string="Barcode", readonly=True, store=True)
    image = fields.Image(string="Captured Photo", required=True, max_width=1920, max_height=1920)
    uploaded_by = fields.Many2one('res.users', string="Uploaded By", default=lambda self: self.env.user, readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], default='draft', string="Status", tracking=True)

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_approve(self):
        for record in self:
            if record.image:
                record.product_id.image_1920 = record.image
                record.state = 'approved'

    def action_reject(self):
        self.state = 'rejected'
