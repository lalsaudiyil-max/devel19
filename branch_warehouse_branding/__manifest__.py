{
    'name': 'Branch Warehouse Branding',
    'version': '1.0',
    'category': 'Sales',
    'summary': 'Link Sales Journals to Warehouses',
    'depends': ['sale_management', 'stock', 'account'],
	'author': 'Anvar Lal K H',
    'data': [
        # Step 1: Install with only security access
        'security/ir.model.access.csv',
        
        # Step 2: Uncomment these one-by-one to find the error
     #   'security/security_rules.xml',
        'views/warehouse_views.xml',
        'views/journal_views.xml',
        'views/user_views.xml',
	#	'views/l10n_sa_invoice_fix.xml',
        'views/report_invoice_inherit.xml',
	#	'views/sale_order_view.xml',
	#	 'views/report_external_layout.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # optional: include JS/CSS if needed
        ],
        'web.assets_frontend': [
            # optional: fonts for frontend if used there
        ],
        'web.report_assets_common': [
          
        ],
    },  # <-- added missing closing brace here
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
