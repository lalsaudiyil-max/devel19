{
    'name': 'Product Image Workflow',
    'version': '1.0',
    'category': 'Inventory',
    'summary': 'Warehouse photo capture and admin approval workflow',
    'depends': ['product', 'stock', 'mail'],
	"author": "Anvar Lal",
    "website": "https://www.mosaco.com",
    'data': [
     #   'security/groups.xml',
	#	'security/security.xml',
        'security/ir.model.access.csv',
        'views/product_image_request_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',

}
