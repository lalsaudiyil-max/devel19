from odoo import models, fields

class ResUsers(models.Model):
  _inherit = 'res.users'
  
  division_id = fields.Many2many('company.division', string='Division')
  
