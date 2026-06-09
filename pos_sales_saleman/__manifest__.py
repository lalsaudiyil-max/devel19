{
    'name': 'POS Sales Salesman',
    'depends': ['point_of_sale','hr'],
    'author': "Anvar Lal",
    'website': "https://www.mosaco.com",
	'license': 'LGPL-3',
	'data': [
	    'views/views.xml',
 	 ],
    'assets': {
        'point_of_sale._assets_pos': [
			'pos_sales_saleman/static/src/js/pos_store.js',
			'pos_sales_saleman/static/src/js/pos_order.js',
			'pos_sales_saleman/static/src/xml/partner_list_unlock.xml',
            'pos_sales_saleman/static/src/xml/pos_orderline.xml',
			
			'pos_sales_saleman/static/src/xml/pos_order.xml',
			'pos_sales_saleman/static/src/xml/product_card.xml',
        ],
	
    },
}
