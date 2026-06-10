from odoo import models, fields, api


class ZatcaImportWizard(models.TransientModel):
    _name = 'zatca.import.wizard'
    _description = 'ZATCA Archive Import Filter Wizard'

    date_from = fields.Date(string='From Date', help="Include invoices on or after this date")
    date_to = fields.Date(string='To Date', help="Include invoices on or before this date")
    journal_name = fields.Char(string='Journal Filter', help="Match Odoo 14 Journal Name or Code (e.g., INV, POS)")

    def action_execute_import(self):
        self.ensure_one()
        archive_model = self.env['zatca.archive.invoice']
        
        # Clean Odoo's default boolean False down to clean query parameters
        d_from = self.date_from if self.date_from else None
        d_to = self.date_to if self.date_to else None
        j_name = self.journal_name.strip() if self.journal_name else None

        # Trigger your core processing logic with sanitized parameters
        action = archive_model.import_from_odoo14(
            date_from=d_from,
            date_to=d_to,
            journal_name=j_name
        )
        return action

