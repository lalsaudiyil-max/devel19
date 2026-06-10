{
    'name': 'Tailoring Trading Management',
    'version': '1.0',
    'category': 'Sales/Tailoring',
    'summary': 'Front-end Retail: Measurements, Bundles, and Master Cutting Fees',
    'author': 'Anvar Lal',
    'depends': ['sale', 'hr', 'analytic', 'product', 'account','mrp'],
    'data': [
        #'security/tailoring_security.xml',
        'security/ir.model.access.csv',
        'data/sequence_data.xml',
        'wizard/tailoring_wizard_views.xml', # Load wizard first
        'views/garment_config_views.xml',
        'views/product_views.xml',           # Load menus/products
        'views/tailoring_order_views.xml',
        'views/tailoring_order_views_2.xml',		# Load orders
        'views/partner_views.xml',   # Load orders		
        'reports/tailoring_report.xml',
        'reports/job_card_view.xml',
    ],
    'application': True,
    'license': 'LGPL-3',
}
