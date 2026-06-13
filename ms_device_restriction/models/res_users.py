from odoo import models, fields

class ResUsers(models.Model):
    _inherit = 'res.users'

    enable_device_restriction = fields.Boolean(
        string='Hardware Gatekeeper Active',
        default=False,
        help="If checked, this specific user can only log in from authorized hardware fingerprints."
    )
