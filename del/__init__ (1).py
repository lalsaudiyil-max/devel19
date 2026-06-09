{
    "name": "POS Branding (Branch Logo & Screensaver)",
    "version": "19.0.1.0.0",
    "category": "Point of Sale",
    "depends": ["point_of_sale"],
    'author': 'Anvar Lal K H',
    'license': 'LGPL-3',
    "data": [
        "views/pos_config_views.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "pos_branch_branding/static/src/js/chrome_patch.js",
            "pos_branch_branding/static/src/xml/navbar.xml",
            "pos_branch_branding/static/src/xml/saver_screen.xml",
            "pos_branch_branding/static/src/scss/branding.scss",
        ],
    },
    "installable": True,
    "application": False,
}
