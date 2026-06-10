# -*- coding: utf-8 -*-

from odoo import models


class DailyInvoicePaymentReport(models.AbstractModel):
    _name = 'daily.invoice.payment.report'
    _description = 'Daily Invoice Payment Report'

    def _get_report_values(self, docids, data=None):

        docs = self.env[
            'daily.invoice.payment.wizard'
        ].browse(docids)

        return {
            'doc_ids': docids,
            'doc_model': 'daily.invoice.payment.wizard',
            'docs': docs,
        }
