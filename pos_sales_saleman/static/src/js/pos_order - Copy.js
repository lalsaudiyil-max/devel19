/** @odoo-module **/

import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";

patch(PosOrder.prototype, {
    /**
     * In Odoo 19, the model stores server data. 
     * We create a getter that can be called from any XML template.
     */
    get invoice_name() {
        // If the order was loaded from the server, account_move is typically [id, name]
        if (this.account_move.name) {
            return this.account_move.name;
        }

		
        // Fallback for manually assigned values
        return this.name || "";
    },
	get logo() {
        // If the order was loaded from the server, account_move is typically [id, name]
		

		if (this.name.toLowerCase().includes("raymond")) {
			console.log("raymond");
			return "raymond";
  
		} else if (this.name.toLowerCase().includes("dishdasha")) {
			return "dishdasha";
		} else if (this.name.toLowerCase().includes("kashmir")) {
			return "kashmir";
		} else {
			return null;
		}
		
    },
	getTotalDiscount() {
        // Use this.lines to access the collection of order lines
        return this.lines.reduce((total, line) => {
            // Only calculate discount if the user manually set a discount %
            // This ignores the difference between Public Price and Pricelist Price
            if (line.discount > 0) {
				
				const lineVat = (line.getDisplayPrice() - line.getBasePrice())/line.getBasePrice();
				console.log(line.getBasePrice());
				console.log(line.getDisplayPrice());
				console.log(lineVat);
                const priceBeforeDiscount = line.getUnitPrice() * line.getQuantity();
                return total + (priceBeforeDiscount * (line.discount / 100))*(1+lineVat);
            }
            return total;
        }, 0);
    },
});



