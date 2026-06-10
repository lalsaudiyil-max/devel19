from odoo import models, fields

class HrEmployee(models.Model):
  _inherit = 'hr.employee'
  
  division_id = fields.Many2many('company.division', string='Division')
  
