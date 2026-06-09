/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { SelectionPopup } from "@point_of_sale/app/components/popups/selection_popup/selection_popup";
import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";
// 1. Patch ProductScreen for the logic


import { Orderline } from "@point_of_sale/app/components/orderline/orderline";


patch(ProductScreen.prototype, {

     onNumpadClick(buttonValue) {

        const line =
            this.currentOrder?.getSelectedOrderline?.();
        const isNumeric =
        /^[0-9.]$/.test(buttonValue);
        // store current UI mode
        if (
            line &&
            ["quantity", "discount", "price"].includes(buttonValue)
        ) {
			
            line.ui_mode = buttonValue;
			line.cashier_discount =
            this.pos?.cashier?.cashier_discount_limit || 0;

            console.log("MODE SET:", buttonValue);
			 console.log("Cashier Discount:", line.cashier_discount);
        }
		 if(isNumeric){
       if(line.ui_mode === "price" && line.product_id.lst_price > 0 ){
		   line.price_unit= line.product_id.lst_price + line.price_extra;
		  return ;
	   }
		  if(line.ui_mode === "discount" && line.ui_discount > 0 ){
			  line.discount=line.ui_discount;
		     return ;
	   }
		 }
		  console.log("ui disc", line.ui_discount);
       const result =
            super.onNumpadClick(...arguments);

        if (line?.validation_error) {

            this.env.services.notification.add(
                line.validation_error,
                {
                    type: "danger",
                }
            );

            line.validation_error = null;
        }

        return result;
    },
});

patch(Orderline.prototype, {
    get salesPersonName() {
        return this.props.line.line_salesman_id
            ? this.props.line.line_salesman_id.name
            : "";
    },

    clone() {
        const cloned = super.clone(...arguments);
        cloned.props.line.line_salesman_id = this.props.line.line_salesman_id;
        return cloned;
    },
});
patch(ProductScreen.prototype, {
    async onSelectSalesman() {
        // We simply call the logic we added to the PosStore
        // Pass 'false' because we only want to affect the selected line via the 
		//this.config = this.pos.data.models["pos.config"].getFirst();
		console.log(this.pos.config.x_avatar_image);
		console.log("here");
        await this.pos.onSelectSalesmanPOS(false);
    }
});

patch(PosStore.prototype, {
    async onSelectSalesmanPOS() {
			
        const dialogService = this.env.services.dialog;
        const allEmployees = this.models['hr.employee']?.getAll() || [];

        if (allEmployees.length === 0) {
            alert("No employees found. Please check POS settings.");
            return;
        }

        dialogService.add(SelectionPopup, {
            title: "Select Salesman",
            list: allEmployees.map(e => ({ id: e.id, label: e.name, item: e })),
            getPayload: (selected) => {
                if (selected) {
                    const order = this.get_order ? this.get_order() : this.getOrder();
                    const currentLine = order?.get_selected_orderline ? order.get_selected_orderline() : order?.getSelectedOrderline();

                    // If a specific line is selected, assign to that line
                    if (currentLine) {
						if (currentLine.price_unit  === 0.01) {
								alert("Price not valid...May be you are scanning the product in Tailoring Counter")
								return;
							}
                        currentLine.line_salesman_id = selected.id;
                        currentLine.line_salesman_name = selected.name;
						console.log("Assigned to one lines");
                        
                    } 
                    
                    // If NO line is selected, OR if you want to ensure ALL lines are updated
                    // We check if currentLine is null or if you just want to force update all:
                    if (!currentLine ) {
                        order.lines.forEach(line => {
							if (line.price_unit  === 0.01) {
								alert("Price not valid...May be you are scanning the product in Tailoring Counter")
								return;
							}
                            line.line_salesman_id = selected.id;
                            line.line_salesman_name = selected.name;
                        });
                        console.log("Assigned to all lines");
                    }
                }
            },
        });
    }
});



patch(PosStore.prototype, {
    async pay() {
        const currentOrder = this.getOrder(); // Matches your code's getter

        // 1. If no partner is selected, force the selection screen

		const missingSalesman = currentOrder.lines.some(
            (line) => !line.line_salesman_id
        );

        if (missingSalesman) {
          
            
			const confirmed = await this.onSelectSalesmanPOS(true);
            if (!confirmed) {
				
				return;
			}
          
        }
        // 3. If partner is already set, proceed normally.
        return await super.pay();
    },
});


patch(PosOrderline.prototype, {

    /**

     * In Odoo 19, serialize is often the primary method 

     * used to package data for the server.

     */

        // To ensure the data stays if you switch screens or reload
    getUnitPrice(){
		const ProductPrice = this.models["decimal.precision"].find(
			(dp) => dp.name === "Product Price"
				);
		 console.log("1:");
		return ProductPrice.round(this.price_unit || 0);
	},
   
        
	setUnitPrice(price) {
        // Keep the normal behavior
		
        super.setUnitPrice(...arguments);
		 console.log("2:");
        const product = this.product_id;
		
		if (!product || !product.lst_price) {
			
            return;
        }
        const lst_price = product.lst_price + this.price_extra ;
		  console.log("Price Extra:", this.price_extra);
        // Get the shop pricelist price from POS order: changes this.getUnitPrice to this.getPrice
		
        const  best_price = this.getUnitPrice(product,this.quantity);
		
        
		
         console.log("Discount Limit:", product.discount_limit);
	    
        // Choose the best (lowest) price
       if (best_price  === 0.01) {
			alert("Price not valid...May be you are scanning the product in Tailoring Counter")
		   this.ui_discount =0.01;
			return;
		}
		
        // Calculate discount if needed
        if (best_price < lst_price && lst_price > 0) {
            const discount = ((lst_price - best_price) / lst_price) * 100;
           
			this.price_unit = lst_price ;
			console.log("UI mode:", this.ui_mode);
			
			this.ui_discount = Math.round(discount * 100) / 100;
            this.setDiscount(Math.round(discount * 100) / 100);
			
           
			console.log("Discount Limit:", product.discount_limit);
        } else {
			
			console.log("Discount Limit:", product.discount_limit);
			this.ui_discount=0;
            this.setDiscount(0);
            this.price_unit = lst_price;
        }
		

    },

	setDiscount(discount) {

        console.log("ORDERLINE MODE:", this.ui_mode);
       console.log("UI discount",  this.ui_discount);
		const product = this.product_id;
		const productLimit=product?.discount_limit;
		const cashierLimit=this.cashier_discount;
		//const allowed = Math.max(product?.discount_limit || 0,this.cashier_discount || 0);
		let allowed;
			if (productLimit === -1) {
  			  allowed = 0;
				} else {
  			  allowed = Math.max(
    		    productLimit || 0,
      			  cashierLimit || 0
   				 );
						}
		  console.log("Allowed",  allowed);
		  console.log("product",  product?.discount_limit);
		  console.log("Cashier",  this.cashier_discount);
        if (this.ui_mode === "discount") {

           // const allowed = 10;
              //  this.product.discount_limit || 0;
           			
           if (discount > allowed) {
                this.discount= this.ui_discount;
            this.validation_error =
                `Max discount allowed is ${allowed}%`;

            return;
                                 }
              
             this.validation_error = null;

           
        }
       // if (this.ui_mode === "price") {

            //const allowed = 10;
              //  this.product.discount_limit || 0;
           
      //      if (discount > allowed) {
       //       this.price_unit = product.lst_price;
				 
			//	 this.setDiscount(this.ui_discount);
           //    this.validation_error =
         //       `Max discount allowed is ${allowed}%`;

        //    return;
        //    }
		//	 this.validation_error = null;
      //  }
        return super.setDiscount(...arguments);
    },


});
