{
    "name": "Stock Lot Import",
    "version": "1.0",
    "summary": "Import inventory with lot numbers",
    "depends": ["stock"],
    "author": "Anvar Lal",
    "license": "OEEL-1",
    "data": [
        "security/ir.model.access.csv",
        "views/stock_inventory_views.xml",
        "views/stock_lot_import_wizard_views.xml",
    ],
    "installable": True,
    "application": False,
}
