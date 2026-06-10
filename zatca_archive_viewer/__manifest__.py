{
    "name": "ZATCA Archive Viewer",
    "version": "1.0",
    "depends": ["base","account","mail","l10n_sa_edi","account_edi_ubl_cii"],
    'author': "Anvar Lal",
    'website': "https://www.mosaco.com",
	'license': 'LGPL-3',
    "data": [
        "security/ir.model.access.csv",
        "views/invoice_views.xml",
        "views/import_wizard.xml",
        "views/res_config_settings_views.xml",
        "reports/invoice_report.xml",
    ],
    "installable": True,
    "application": True,
}
