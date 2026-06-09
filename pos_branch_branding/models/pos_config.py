from odoo import models, fields


class PosConfig(models.Model):
    _inherit = "pos.config"

    branch_logo = fields.Image(string="Branch Logo")
    screensaver_logo = fields.Image(string="Screensaver Logo")
    browser_title = fields.Char(string="Browser Tab Title")

    
