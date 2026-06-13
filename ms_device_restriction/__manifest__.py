{
    'name': 'Device Login Restriction',
    'version': '19.0.1.0.0',
    'summary': 'Restrict user logins to approved and trusted devices,.',
    'category': 'Human Resources/Security',
    'author': 'Anvar Lal K H',
    'depends': ['base', 'web', 'sale', 'purchase'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_users_views.xml',
        'views/login_templates.xml',
        'views/device_views.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'ms_device_restriction/static/src/js/hardware_gatekeeper.js',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
