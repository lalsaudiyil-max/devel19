from odoo import models, fields, api, _
from odoo.exceptions import AccessError

class ResUsersDevice(models.Model):
    _name = 'res.users.device'
    _description = 'Authorized User Devices'
    _rec_name = 'computer_name'

    user_id = fields.Many2one(
        'res.users', 
        string='Authorized User', 
        required=True, 
        ondelete='cascade',
        index='btree_not_null' # Modern indexing property
    )
    
    hardware_uuid = fields.Char(
        string='Permanent Hardware ID', 
        required=True,
        index='btree_not_null' # Modern indexing property
    )
    
    computer_name = fields.Char(string='Computer Terminal Name', default='Unassigned Workstation')
    
    state = fields.Selection([
        ('pending', 'Pending Authorization'),
        ('approved', 'Approved / Whitelisted'),
        ('blocked', 'Blocked / Blacklisted')
    ], string='Authorization Status', default='pending', required=True)
    
    last_login = fields.Datetime(string='Last Valid Connection', readonly=True)

    # MODERN ODOO ALTERNATIVE TO _sql_constraints:
    # We use python validation decorators to enforce multi-field uniqueness 
    # cleanly before writing to PostgreSQL.
    @api.constrains('user_id', 'hardware_uuid')
    def _check_unique_user_hardware(self):
        for record in self:
            duplicate = self.search([
                ('id', '!=', record.id),
                ('user_id', '=', record.user_id.id),
                ('hardware_uuid', '=', record.hardware_uuid)
            ], limit=1)
            if duplicate:
                raise AccessError(_("This device footprint is already registered to this user!"))

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_block(self):
        self.write({'state': 'blocked'})
