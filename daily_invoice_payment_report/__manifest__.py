# -*- coding: utf-8 -*-

{
    'name': 'Daily Invoice Payment Report',
    'version': '19.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Invoice and payment report by salesperson',
    'author': 'Anvar Lal K H',
    'license': 'LGPL-3',
    'depends': [
        'account',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/daily_invoice_payment_wizard_views.xml',
        'report/daily_invoice_payment_report.xml',
        'report/daily_invoice_payment_templates.xml',
    ],
    'installable': True,
    'application': False,
}
