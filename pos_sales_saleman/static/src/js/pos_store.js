/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { SelectionPopup } from "@point_of_sale/app/components/popups/selection_popup/selection_popup";
import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
// 1. Patch ProductScreen for the logic


import { Orderline } from "@point_of_sale/app/components/orderline/orderline";

import { ProductCard } from "@point_of_sale/app/components/product_card/product_card";


patch(ProductCard.prototype, {
    setup() {
        super.setup(...arguments);
        this.pos = usePos(); 
    },

    

	get discountData() {
  		const productD =
   	 		this.pos.models["product.template"]
        	?.get(this.props.productId)
        	?.product_variant_ids?.[0];
		const product = this.props.product;
		

    	if (!product) {
        	return null;
    	}
		const productLimit=productD?.discount_limit;
		let originalPrice = product.list_price;
		let currentPrice = product.getPrice(this.pos.config.pricelist_id, 1) ;
		

    	let hasDiscount = false;
		let discountPercentage = 0;

		if (originalPrice > currentPrice && currentPrice > 0) {
    		hasDiscount = true;

    		discountPercentage =
        		((originalPrice - currentPrice) / originalPrice) * 100;

    		if (typeof product.getTaxDetails === "function") {
        		const taxDetailsOriginal = product.getTaxDetails(originalPrice);

        		originalPrice =
            		taxDetailsOriginal?.total_included || originalPrice;

        		currentPrice =
            		currentPrice * originalPrice / product.list_price;
    		}

    		return {
        		originalPriceFormatted:
            		this.env.utils.formatCurrency(originalPrice),

        		currentPriceFormatted:
            		this.env.utils.formatCurrency(currentPrice),

        		discountPercentage:
            		Math.round(discountPercentage) + "%",

        		hasDiscount: true,

        		showDiscountLimit: false,
    		};
		}

		// No active discount
		if (product.discount_limit > 0) {

    		let listPrice = product.list_price;

    		if (typeof product.getTaxDetails === "function") {
        		const taxDetails = product.getTaxDetails(listPrice);
        		listPrice = taxDetails?.total_included || listPrice;
    		}

    		return {
        		originalPriceFormatted:
            		this.env.utils.formatCurrency(listPrice),

        		currentPriceFormatted:
            		this.env.utils.formatCurrency(listPrice),

        		discountLimit: productLimit,

        		hasDiscount: false,

        		showDiscountLimit: true,
    		};
		}

		return null;
	}
});

	

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

patch(Orderline.prototype,{
    setup() {
        super.setup(...arguments);
        this.discount = 0;
		
        this.ui_discount = 0;
        this.ui_mode = null;
		//console.log(this.discount);
    },
	  
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
		//console.log(this.pos.config.x_avatar_image);
		//console.log("here");
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
								line.setDiscount(0);
								return;
							}
                        currentLine.line_salesman_id = selected.id;
                        currentLine.line_salesman_name = selected.name;
						
                        
                    } 
                    
                    // If NO line is selected, OR if you want to ensure ALL lines are updated
                    // We check if currentLine is null or if you just want to force update all:
                    if (!currentLine ) {
                        order.lines.forEach(line => {
							if (line.price_unit  === 0.01) {
								alert("Price not valid...May be you are scanning the product in Tailoring Counter")
								line.setDiscount(0);
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
		
		return ProductPrice.round(this.price_unit || 0);
	},
   
        
	setUnitPrice(price) {
        // Keep the normal behavior
		
        super.setUnitPrice(...arguments);
		
        const product = this.product_id;
		
		if (!product || !product.lst_price) {
			this.setDiscount(0);
            return;
        }
        const lst_price = product.lst_price + this.price_extra ;
		
        // Get the shop pricelist price from POS order: changes this.getUnitPrice to this.getPrice
		
        const  best_price = this.getUnitPrice(product,this.quantity);
		
        
		
        
	    
        // Choose the best (lowest) price
       if (best_price  === 0.01) {
			alert("Price not valid...May be you are scanning the product in Tailoring Counter")
		   this.ui_discount =0;
		   this.setDiscount(0);
			return;
		}
		
        // Calculate discount if needed
        if (best_price < lst_price && lst_price > 0) {
            const discount = ((lst_price - best_price) / lst_price) * 100;
           
			this.price_unit = lst_price ;
			
			
			this.ui_discount = Math.round(discount * 100) / 100;
            this.setDiscount(Math.round(discount * 100) / 100);
			
           
			
        } else {
			
			
			this.ui_discount=0;
            this.setDiscount(0);
            this.price_unit = lst_price;
        }
		

    },

	setDiscount(discount) {

       
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
