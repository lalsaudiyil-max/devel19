from odoo import models, fields

class Division(models.Model):
  _name = 'company.division'
  _description = 'Division'
  
  name = fields.Char(string='Division', required=True)
  product_ids = fields.One2many('product.template', 'division_id', string='Products')
  employee_ids= fields.Many2many('hr.employee',  string='Employees')
  partner_ids = fields.Many2many('res.partner',  string='Partners')
  user_ids = fields.Many2many('res.users',  string='Users')
  
