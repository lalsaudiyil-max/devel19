# -*- coding: utf-8 -*-
from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # The config_parameter namespace maps these fields directly to the ir.config_parameter model
    legacy_db_name = fields.Char(
        string="Legacy Database Name", 
        config_parameter='zatca_archive_viewer.legacy_db_name'
    )
    legacy_db_user = fields.Char(
        string="Legacy DB User", 
        config_parameter='zatca_archive_viewer.legacy_db_user',
        default="postgres"
    )
    legacy_db_password = fields.Char(
        string="Legacy DB Password", 
        config_parameter='zatca_archive_viewer.legacy_db_password'
    )
    legacy_db_host = fields.Char(
        string="Legacy DB Host", 
        config_parameter='zatca_archive_viewer.legacy_db_host',
        default="localhost"
    )
    legacy_db_port = fields.Integer(
        string="Legacy DB Port", 
        config_parameter='zatca_archive_viewer.legacy_db_port',
        default=5432
    )
