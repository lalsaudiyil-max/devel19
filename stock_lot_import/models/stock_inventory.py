import base64
import io
import csv
import pandas as pd

from odoo import models, fields, _
from odoo.exceptions import UserError


class StockLotImportWizard(models.TransientModel):
    _name = "stock.lot.import.wizard"
    _description = "Import Inventory with Lots"

    file = fields.Binary(required=True)
    filename = fields.Char()

    def action_import(self):
        if not self.file:
            raise UserError("Please upload a file.")

        file_data = base64.b64decode(self.file)
        
        # Detect format
        if self.filename and self.filename.endswith(".csv"):
            data = self._read_csv(file_data)
        else:
            data = self._read_excel(file_data)

        errors = []

        for i, row in enumerate(data, start=1):
            try:
                self._process_row(row)
            except Exception as e:
                errors.append(f"Line {i}: {str(e)}")

        if errors:
            raise UserError("\n".join(errors))

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Import Completed"),
                "message": _("Inventory lines updated successfully"),
                "type": "success",
            },
        }

    def _read_csv(self, file_data):
        file = io.StringIO(file_data.decode("utf-8-sig"))
        return list(csv.DictReader(file))

    def _read_excel(self, file_data):
        df = pd.read_excel(io.BytesIO(file_data))
        return df.to_dict(orient="records")

    def _process_row(self, row):
        product_code = row.get("product_code")
        lot_name = row.get("lot")
        qty = float(row.get("qty", 0))
        location_name = row.get("location")

        if not product_code:
            raise UserError("Missing product_code")

        product = self.env["product.product"].search(
            [("default_code", "=", product_code)], limit=1
        )
        if not product:
            raise UserError(f"Product not found: {product_code}")

        location = self.env["stock.location"].search(
            [("complete_name", "ilike", location_name)], limit=1
        )
        if not location:
            raise UserError(f"Location not found: {location_name}")
        if not lot_name:
            raise UserError(f"Lot not found: {lot_name}")

        lot = None
        
        if lot_name:
            lot = self.env["stock.lot"].search([
                ("name", "=", lot_name),
                ("product_id", "=", product.id)
            ], limit=1)
            
            if not lot:
                lot = self.env["stock.lot"].create({
                    "name": lot_name,
                    "product_id": product.id,
                })
                 
            quant = self.env["stock.quant"].search([
                ("product_id", "=", product.id),
                ("location_id", "=", location.id),
                ("lot_id", "=", lot.id if lot else False),
            ], limit=1)

            if quant:
                quant.with_context(inventory_mode=True).write({
                    "inventory_quantity": qty
                })
            else:
                self.env["stock.quant"].with_context(inventory_mode=True).create({
                    "product_id": product.id,
                    "location_id": location.id,
                    "lot_id": lot.id if lot else False,
                    "inventory_quantity": qty,
                })
