from odoo import models, fields, api
from datetime import date

class ResPartner(models.Model):
  _inherit = 'res.partner'
  
  division_id = fields.Many2many('company.division', string='Division')
  nationality_id = fields.Many2one('res.country', string='Nationality')
  date_of_birth = fields.Date(string='Date of Birth')
  age = fields.Integer(string='Age', compute='_compute_age', store=True)

  @api.depends('date_of_birth')
  def _compute_age(self):
    today= date.today()
    for rec in self:
      if rec.date_of_birth:
        rec.age= today.year- rec.date_of_birth.year - ((today.month,today.day)<(rec.date_of_birth.month,rec.date_of_birth.day))
      else:
        rec.age=0
