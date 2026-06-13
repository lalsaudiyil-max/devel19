from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    enable_device_restriction = fields.Boolean(
        string="Strict Hardware Gatekeeper",
        help="When enabled, unapproved browser fingerprints will be blocked from logging in.",
        config_parameter='ms_device_restriction.enable_device_restriction',
        default=True
    )
