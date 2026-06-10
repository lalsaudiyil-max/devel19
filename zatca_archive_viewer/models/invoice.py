from odoo import models, fields, api
from odoo.tools import config

import logging
import psycopg2

_logger = logging.getLogger(__name__)


# =========================================================
# ARCHIVE INVOICE
# =========================================================

class ZatcaArchiveInvoice(models.Model):
    _name = "zatca.archive.invoice"
    _description = "ZATCA Archive Invoice"
    _order = "invoice_date desc, id desc"

    _inherit = ['mail.thread','mail.activity.mixin']

    # =====================================================
    # BASIC
    # =====================================================

    name = fields.Char(string="Invoice Reference")
    historical_csid = fields.Char(string="Signing CSID Reference")
    
    # Store parsed data fields directly on your model to easily display them on your PDF layout
    

    legacy_move_id = fields.Integer(
        index=True,
        readonly=True
    )

    invoice_date = fields.Date(
        index=True,
        readonly=True
    )

    create_date_legacy = fields.Datetime(readonly=True)

    move_type = fields.Selection([
        ("out_invoice", "Invoice"),
        ("out_refund", "Credit Note"),
    ], index=True)

    state = fields.Selection([
        ("draft", "Draft"),
        ("posted", "Posted"),
        ("cancel", "Cancelled"),
    ], index=True)

    # =====================================================
    # CUSTOMER SNAPSHOT
    # =====================================================

    customer_id_legacy = fields.Integer(index=True)

    customer_name = fields.Char(
        index=True,
        readonly=True
    )

    customer_vat = fields.Char(
        index=True,
        readonly=True
    )

    customer_phone = fields.Char(
        index=True,
        readonly=True
    )

    customer_mobile = fields.Char(
        index=True,
        readonly=True
    )

    customer_email = fields.Char(
        index=True,
        readonly=True
    )

    customer_country = fields.Char(readonly=True)

    customer_city = fields.Char(
        index=True,
        readonly=True
    )

    customer_district = fields.Char(readonly=True)

    customer_street = fields.Char(readonly=True)

    customer_street2 = fields.Char(readonly=True)

    customer_zip = fields.Char(readonly=True)

    # =====================================================
    # SELLER SNAPSHOT
    # =====================================================

    seller_name = fields.Char(
        index=True,
        readonly=True
    )

    seller_vat = fields.Char(
        index=True,
        readonly=True
    )

    seller_phone = fields.Char(readonly=True)

    seller_email = fields.Char(readonly=True)

    seller_country = fields.Char(readonly=True)

    seller_city = fields.Char(readonly=True)

    seller_street = fields.Char(readonly=True)

    seller_street2 = fields.Char(readonly=True)

    seller_zip = fields.Char(readonly=True)

    # =====================================================
    # SALES / BRANCH
    # =====================================================

    company_name = fields.Char(
        index=True,
        readonly=True
    )

    branch_name = fields.Char(
        index=True,
        readonly=True
    )

    sales_team = fields.Char(
        index=True,
        readonly=True
    )

    salesperson = fields.Char(
        index=True,
        readonly=True
    )

    journal_name = fields.Char(
        index=True,
        readonly=True
    )

    currency_name = fields.Char(readonly=True)

    # =====================================================
    # ZATCA
    # =====================================================

    zatca_uuid = fields.Char(
        index=True,
        readonly=True
    )

    zatca_invoice_hash = fields.Char(
        index=True,
        readonly=True
    )

    zatca_previous_hash = fields.Char(
        index=True,
        readonly=True
    )

    zatca_qr = fields.Text(readonly=True)

    zatca_status = fields.Char(
        index=True,
        readonly=True
    )

    # =====================================================
    # TOTALS
    # =====================================================

    amount_untaxed = fields.Float(readonly=True)

    amount_tax = fields.Float(readonly=True)

    amount_total = fields.Float(readonly=True)

    amount_discount = fields.Float(readonly=True)
    l10n_sa_qr_code_str = fields.Text(string="ZATCA QR Code Payload String")


    # =====================================================
    # LINES
    # =====================================================

    line_ids = fields.One2many(
        "zatca.archive.line",
        "invoice_id",
        readonly=True
    )

    # =====================================================
    # SQL
    # =====================================================

    _unique_legacy_move = models.Constraint(
        'UNIQUE(legacy_move_id)',
        'Invoice already archived.'
    )
        
    # =====================================================
    # CONNECTION
    # =====================================================
    def action_parse_stored_xml(self):
        """
        Reads the attached historical XML file, parses the total amount,
        and extracts the official base64 cryptographic QR data block.
        """
        attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'zatca.archive.invoice'),
            ('res_id', '=', self.id),
            ('mimetype', '=', 'text/xml')
        ], limit=1)
        
        if not attachment:
            _logger.warning("No XML attachment found to parse for Archive ID %s", self.id)
            return

        try:
            # 1. Gather raw data and build root DOM element tree
            xml_data = attachment.raw or base64.b64decode(attachment.datas)
            parser = etree.XMLParser(recover=True, remove_blank_text=True)
            root = etree.fromstring(xml_data, parser=parser)
            
            # 2. Define standard ZATCA / UBL 2.1 Namespaces
            namespaces = {
                'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
                'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2'
            }
            
            # 3. Parse total inclusive financial values
            total_nodes = root.xpath('//cbc:TaxInclusiveAmount/text()', namespaces=namespaces)
            if total_nodes:
                self.amount_total = float(total_nodes[0])

            # =================================================================
            # 4. PARSE THE QR CODE DATA STRING
            # =================================================================
            # This XPath filters Document References specifically where the sibling ID element equals 'QR'
            qr_nodes = root.xpath(
                '//cac:AdditionalDocumentReference[cbc:ID="QR"]//cbc:EmbeddedDocumentBinaryObject/text()', 
                namespaces=namespaces
            )
            
            if qr_nodes:
                # Strip out any unexpected formatting line breaks or trailing spaces from raw XML nodes
                self.zatca_qr_text = qr_nodes[0].strip()
                _logger.info("Successfully extracted ZATCA QR Code text for Archive Record ID: %s", self.id)
            else:
                _logger.warning("No AdditionalDocumentReference node matching ID 'QR' found in document.")

        except Exception as e:
            _logger.error("Failed executing core XML extraction task: %s", str(e))

    
    

    def _get_conn(self):

        get_param = self.env['ir.config_parameter'].sudo().get_param
    
        try:
            return psycopg2.connect(
                dbname=get_param('zatca_archive_viewer.legacy_db_name'),
                user=get_param('zatca_archive_viewer.legacy_db_user', 'postgres'),
                password=get_param('zatca_archive_viewer.legacy_db_password'),
                host=get_param('zatca_archive_viewer.legacy_db_host', 'localhost'),
                port=int(get_param('zatca_archive_viewer.legacy_db_port', 5432))
            )
        except Exception as e:
            _logger.error(f"Failed connecting to ZATCA legacy archive database server: {str(e)}")
            raise

    # =====================================================
    # IMPORT MAIN
    # =====================================================

    
        
    @api.model
    def import_from_odoo14(self, date_from=False, date_to=False, journal_name=False):

        if not date_from:
            raise UserError(
                "Migration aborted: 'From Date' is mandatory."
            )

        if not date_to:
            raise UserError(
                "Migration aborted: 'To Date' is mandatory."
            )

        if not journal_name:
            raise UserError(
                "Migration aborted: 'Journal Name' is mandatory."
            )

        conn = None
        counter = 0
        failed = 0

        try:

            conn = self._get_conn()

            

            named_cursor = conn.cursor(
                name="zatca_archive_cursor"
            )

            query = """
                SELECT am.id
                FROM account_move am
                JOIN account_journal aj
                    ON aj.id = am.journal_id
                WHERE am.move_type IN ('out_invoice', 'out_refund')
                  AND am.invoice_date >= %(date_from)s
                  AND am.invoice_date <= %(date_to)s
                  AND aj.name ILIKE %(journal_name)s
            """

            params = {
                'date_from': date_from,
                'date_to': date_to,
                'journal_name': f"%{journal_name}%"
            }

            

            named_cursor.execute(query, params)

            while True:

                rows = named_cursor.fetchmany(200)

                if not rows:
                    break

                for row in rows:

                    move_id = row[0]

                    try:

                        with self.env.cr.savepoint():

                            self._import_single(
                                conn,
                                move_id
                            )

                            counter += 1

                        # notify every 100 invoices only
                            if counter % 100 == 0:

                                _logger.info(
                                    "Imported %s invoices",
                                    counter
                                )

                                self.env['bus.bus']._sendone(
                                    self.env.user.partner_id,
                                    'simple_notification',
                                    {
                                        'title': 'Import Progress',
                                        'message': (
                                            f'{counter} invoices imported successfully'
                                        ),
                                        'sticky': False,
                                        'warning': False,
                                    }
                                )

                    except Exception as move_error:

                        failed += 1

                        _logger.exception(
                            "Failed importing move %s",
                            move_id
                        )

                        self.env['bus.bus']._sendone(
                            self.env.user.partner_id,
                            'simple_notification',
                            {
                                'title': 'Invoice Import Failed',
                                'message': (
                                    f'Invoice ID {move_id} failed: '
                                    f'{str(move_error)}'
                                ),
                                'sticky': False,
                                'warning': True,
                            }
                        )

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sync Completed',
                    'message': (
                        f'Synchronization completed. '
                        f'Success: {counter}, Failed: {failed}'
                    ),
                    'type': 'success' if failed == 0 else 'warning',
                    'sticky': failed > 0,
                }
            }

        except Exception as e:

            _logger.exception(
                "Failed importing journal %s",
                journal_name
            )

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Synchronization Failed',
                    'message': str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }

        finally:

            if conn:
                conn.close()
    # =====================================================
    # IMPORT SINGLE
    # =====================================================

    def _import_single(self, conn, move_id):

        # =================================================
        # SKIP IF ALREADY IMPORTED
        # =================================================
        if self.search([
            ("legacy_move_id", "=", move_id)
        ], limit=1):
            return

        with conn.cursor() as cur:

            # =================================================
            # MAIN INVOICE DATA
            # =================================================
            cur.execute("""
                SELECT
                    am.id,
                    am.name,
                    am.invoice_date,
                    am.create_date,
                    am.move_type,
                    am.state,

                    am.amount_untaxed,
                    am.amount_tax,
                    am.amount_total,

                    rc.name,

                    rp.id,
                    rp.name,
                    rp.vat,
                    rp.phone,
                    rp.mobile,
                    rp.email,
                    rp.street,
                    rp.street2,
                    rp.city,
                    rp.zip,

                    country.name,

                    company.name,
                    company.vat,
                    company.phone,
                    company.email,
                    company.street,
                    company.street2,
                    company.city,
                    company.zip,

                    company_country.name,

                    team.name,
                    usr.name,
                    journal.name

                FROM account_move am

                LEFT JOIN res_currency rc
                    ON am.currency_id = rc.id

                LEFT JOIN res_partner rp
                    ON am.partner_id = rp.id

                LEFT JOIN res_country country
                    ON rp.country_id = country.id

                LEFT JOIN res_company company_rec
                    ON am.company_id = company_rec.id

                LEFT JOIN res_partner company
                    ON company_rec.partner_id = company.id

                LEFT JOIN res_country company_country
                    ON company.country_id = company_country.id

                LEFT JOIN crm_team team
                    ON am.team_id = team.id

                LEFT JOIN res_users usr_rec
                    ON am.invoice_user_id = usr_rec.id

                LEFT JOIN res_partner usr
                    ON usr_rec.partner_id = usr.id

                LEFT JOIN account_journal journal
                    ON am.journal_id = journal.id

                WHERE am.id = %s
            """, (move_id,))

            row = cur.fetchone()

            if not row:
                return

            (
                legacy_move_id,
                name,
                invoice_date,
                create_date_legacy,
                move_type,
                state,

                amount_untaxed,
                amount_tax,
                amount_total,

                currency_name,

                customer_id_legacy,
                customer_name,
                customer_vat,
                customer_phone,
                customer_mobile,
                customer_email,
                customer_street,
                customer_street2,
                customer_city,
                customer_zip,
                customer_country,

                seller_name,
                seller_vat,
                seller_phone,
                seller_email,
                seller_street,
                seller_street2,
                seller_city,
                seller_zip,
                seller_country,

                sales_team,
                salesperson,
                journal_name

            ) = row

            # =================================================
            # ZATCA DATA (CLEANED)
            # =================================================
            cur.execute("""
                SELECT
                    invoice_uuid,
                    zatca_invoice_hash,
                    zatca_invoice_hash_hex,
                    sa_qr_code_str,
                    l10n_sa_zatca_status
                FROM account_move
                WHERE id = %s
            """, (move_id,))

            zrow = cur.fetchone()

            zatca_uuid = None
            zatca_invoice_hash = None
            zatca_previous_hash = None
            zatca_qr = None
            zatca_status = None

            if zrow:
                (
                    zatca_uuid,
                    zatca_invoice_hash,
                    zatca_previous_hash,
                    zatca_qr,
                    zatca_status
                ) = zrow

            # =================================================
            # DISCOUNT TOTAL
            # =================================================
            cur.execute("""
                SELECT COALESCE(
                    SUM(
                        (quantity * price_unit * discount) / 100
                    ),
                    0
                )
                FROM account_move_line
                WHERE move_id = %s
                  AND display_type IS NULL
            """, (move_id,))

            amount_discount = cur.fetchone()[0] or 0.0

            # =================================================
            # CREATE ARCHIVE RECORD
            # =================================================
            invoice = self.create({

                "legacy_move_id": legacy_move_id,
                "name": name,
                "invoice_date": invoice_date,
                "create_date_legacy": create_date_legacy,
                "move_type": move_type,
                "state": state,

                # customer
                "customer_id_legacy": customer_id_legacy,
                "customer_name": customer_name,
                "customer_vat": customer_vat,
                "customer_phone": customer_phone,
                "customer_mobile": customer_mobile,
                "customer_email": customer_email,
                "customer_country": customer_country,
                "customer_city": customer_city,
                "customer_street": customer_street,
                "customer_street2": customer_street2,
                "customer_zip": customer_zip,

                # seller
                "seller_name": seller_name,
                "seller_vat": seller_vat,
                "seller_phone": seller_phone,
                "seller_email": seller_email,
                "seller_country": seller_country,
                "seller_city": seller_city,
                "seller_street": seller_street,
                "seller_street2": seller_street2,
                "seller_zip": seller_zip,

                # sales
                "company_name": seller_name,
                "branch_name": seller_name,
                "sales_team": sales_team,
                "salesperson": salesperson,
                "journal_name": journal_name,
                "currency_name": currency_name,

                # ZATCA
                "zatca_uuid": zatca_uuid,
                "zatca_invoice_hash": zatca_invoice_hash,
                "zatca_previous_hash": zatca_previous_hash,
                "zatca_qr": zatca_qr,
                "zatca_status": zatca_status,

                # totals
                "amount_untaxed": amount_untaxed,
                "amount_tax": amount_tax,
                "amount_total": amount_total,
                "amount_discount": amount_discount,
            })

            # =================================================
            # LINE IMPORT
            # =================================================
            self._import_lines(cur, move_id, invoice)
    # =====================================================
    # IMPORT LINES
    # =====================================================

    def _import_lines(
        self,
        cur,
        move_id,
        invoice
    ):

        cur.execute("""
            SELECT

                aml.name,

                aml.quantity,

                aml.price_unit,

                aml.discount,

                aml.price_subtotal,

                aml.price_total,

                pt.name,

                pp.default_code,

                pp.barcode,

                uu.name

            FROM account_move_line aml

            LEFT JOIN product_product pp
                ON aml.product_id = pp.id

            LEFT JOIN product_template pt
                ON pp.product_tmpl_id = pt.id

            LEFT JOIN uom_uom uu
                ON aml.product_uom_id = uu.id

            WHERE aml.move_id=%s
            AND aml.display_type IS NULL
            AND aml.account_id in(280,160)

            ORDER BY aml.id
        """, (move_id,))

        rows = cur.fetchall()

        vals_list = []

        for row in rows:

            (
                line_name,

                quantity,

                unit_price,

                discount_percent,

                line_subtotal,

                line_total,

                product_name,

                default_code,

                barcode,

                uom_name

            ) = row

            tax_percent = 0.0

            if line_subtotal:

                tax_percent = (
                    (
                        line_total
                        - line_subtotal
                    )
                    / line_subtotal
                ) * 100

            discount_amount = 0.0

            if (
                quantity
                and unit_price
                and discount_percent
            ):

                discount_amount = (
                    quantity
                    * unit_price
                    * discount_percent
                ) / 100.0

            vals_list.append({

                "invoice_id":
                    invoice.id,

                "name":
                    line_name or product_name,

                "product_name":
                    product_name,

                "default_code":
                    default_code,

                "barcode":
                    barcode,

                "uom_name":
                    uom_name,

                "quantity":
                    quantity,

                "unit_price":
                    unit_price,

                "discount_percent":
                    discount_percent,

                "discount_amount":
                    discount_amount,

                "tax_percent":
                    round(tax_percent, 2),

                "line_subtotal":
                    line_subtotal,

                "line_total":
                    line_total,
            })

        if vals_list:

            self.env[
                "zatca.archive.line"
            ].create(vals_list)


# =========================================================
# ARCHIVE LINE
# =========================================================

class ZatcaArchiveLine(models.Model):
    _name = "zatca.archive.line"
    _description = "ZATCA Archive Invoice Line"

    invoice_id = fields.Many2one(
        "zatca.archive.invoice",
        ondelete="cascade",
        index=True
    )

    # =====================================================
    # PRODUCT
    # =====================================================

    name = fields.Char(
        index=True,
        readonly=True
    )

    product_name = fields.Char(
        index=True,
        readonly=True
    )

    default_code = fields.Char(
        index=True,
        readonly=True
    )

    barcode = fields.Char(
        index=True,
        readonly=True
    )

    uom_name = fields.Char(readonly=True)

    # =====================================================
    # FINANCIALS
    # =====================================================

    quantity = fields.Float(readonly=True)

    unit_price = fields.Float(readonly=True)

    discount_percent = fields.Float(readonly=True)

    discount_amount = fields.Float(readonly=True)

    tax_percent = fields.Float(readonly=True)

    line_subtotal = fields.Float(readonly=True)

    line_total = fields.Float(readonly=True)
