import base64
import logging
import traceback
import io
from lxml import etree
from contextlib import contextmanager
import werkzeug.urls

from odoo import models, fields, api, _
from odoo.tools.pdf import OdooPdfFileReader, OdooPdfFileWriter

_logger = logging.getLogger(__name__)

class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'


# ==========================================
# 1. THE QWEB REPORT DATA ENGINE PARSER
# ==========================================
class ZatcaArchiveReportParser(models.AbstractModel):
    _name = 'report.zatca_archive_viewer.report_archive_document'
    _description = 'ZATCA Archive Report Document Parser Engine'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['zatca.archive.invoice'].browse(docids)
        parsed_docs_map = {}

        for doc in docs:
            attachment = self.env['ir.attachment'].search([
                ('res_model', '=', 'zatca.archive.invoice'),
                ('res_id', '=', doc.id),
                ('mimetype', 'in', ['text/xml', 'application/xml'])
            ], limit=1)

            if not attachment and doc.name:
                normalized_name = doc.name.replace('/', '-')
                attachment = self.env['ir.attachment'].search([
                    ('name', 'ilike', normalized_name),
                    ('mimetype', 'in', ['text/xml', 'application/xml'])
                ], limit=1)

            seller_vals = {
                'name': 'ORIGINAL SELLER RECORD',
                'vat': '', 'building': '', 'street': '', 'city': '', 'zip': '',
                'qr_url': False  # This will store our pre-formatted URL string
            }

            # Gather raw string data
            raw_qr_payload = doc.l10n_sa_qr_code_str or ''

            if attachment:
                try:
                    xml_bytes = attachment.raw or base64.b64decode(attachment.datas)
                    xml_root = etree.fromstring(xml_bytes, parser=etree.XMLParser(recover=True, remove_blank_text=True))
                    
                    ns = {
                        'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
                        'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2'
                    }

                    name_nodes = xml_root.xpath('//cac:AccountingSupplierParty/cac:Party/cac:PartyLegalEntity/cbc:RegistrationName/text()', namespaces=ns)
                    vat_nodes = xml_root.xpath('//cac:AccountingSupplierParty/cac:Party/cac:PartyTaxScheme/cbc:CompanyID/text()', namespaces=ns)
                    building_nodes = xml_root.xpath('//cac:AccountingSupplierParty/cac:Party/cac:PostalAddress/cbc:BuildingNumber/text()', namespaces=ns)
                    street_nodes = xml_root.xpath('//cac:AccountingSupplierParty/cac:Party/cac:PostalAddress/cbc:StreetName/text()', namespaces=ns)
                    city_nodes = xml_root.xpath('//cac:AccountingSupplierParty/cac:Party/cac:PostalAddress/cbc:CityName/text()', namespaces=ns)
                    zip_nodes = xml_root.xpath('//cac:AccountingSupplierParty/cac:Party/cac:PostalAddress/cbc:PostalZone/text()', namespaces=ns)
                    qr_nodes = xml_root.xpath('//cac:AdditionalDocumentReference[cbc:ID="QR"]/cac:Attachment/cbc:EmbeddedDocumentBinaryObject/text()', namespaces=ns)

                    if name_nodes: seller_vals['name'] = name_nodes[0].strip()
                    if vat_nodes: seller_vals['vat'] = vat_nodes[0].strip()
                    if building_nodes: seller_vals['building'] = building_nodes[0].strip()
                    if street_nodes: seller_vals['street'] = street_nodes[0].strip()
                    if city_nodes: seller_vals['city'] = city_nodes[0].strip()
                    if zip_nodes: seller_vals['zip'] = zip_nodes[0].strip()
                    if qr_nodes: raw_qr_payload = qr_nodes[0].strip()
                except Exception:
                    pass

            # SAFELY CONSTRUCT THE URL IN PYTHON TO PREVENT NONE/CONCATENATION BLOCKS
            if raw_qr_payload:
                clean_payload = str(raw_qr_payload).strip()
                if len(clean_payload) > 0:
                    # Leverage werkzeug to handle query escaping completely outside QWeb
                    encoded_param = werkzeug.urls.url_quote(clean_payload)
                    seller_vals['qr_url'] = f"/report/barcode/?barcode_type=QR&value={encoded_param}&width=150&height=150"

            parsed_docs_map[doc.id] = seller_vals

        return {
            'doc_ids': docids,
            'doc_model': 'zatca.archive.invoice',
            'docs': docs,
            'xml_data': parsed_docs_map,
        }

# ==========================================
# 2. THE PDF/A-3B STRUCTURAL WRITER ENGINE
# ==========================================
class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    # =========================================================================
    # NEW HOOK: DYNAMICALLY ENFORCE OFFICIAL ZATCA FILENAME STRUCTURE
    # =========================================================================
    def _get_rendering_basename(self, report_ref, res_ids):
        report = self._get_report_from_name(report_ref)
        
        # Check if this is our targeted ZATCA archive record structure
        if report and report.model == 'zatca.archive.invoice' and len(res_ids) == 1:
            record = self.env['zatca.archive.invoice'].browse(res_ids[0])
            
            # 1. Fetch Seller VAT safely (Default placeholder if missing)
            seller_vat = '300183366500003'
            
            # Attempt to pull from our parsed XML matrix engine if available
            attachment = self.env['ir.attachment'].search([
                ('res_model', '=', 'zatca.archive.invoice'),
                ('res_id', '=', record.id),
                ('mimetype', 'in', ['text/xml', 'application/xml'])
            ], limit=1)
            
            if attachment:
                try:
                    xml_bytes = attachment.raw or base64.b64decode(attachment.datas)
                    xml_root = etree.fromstring(xml_bytes, parser=etree.XMLParser(recover=True))
                    ns = {'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
                          'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2'}
                    vat_nodes = xml_root.xpath('//cac:AccountingSupplierParty/cac:Party/cac:PartyTaxScheme/cbc:CompanyID/text()', namespaces=ns)
                    if vat_nodes:
                        seller_vat = vat_nodes[0].strip()
                    date_nodes = xml_root.xpath('//cbc:IssueDate/text()', namespaces=ns)
                    time_nodes = xml_root.xpath('//cbc:IssueTime/text()', namespaces=ns)
        
                    if date_nodes and time_nodes:
                        # Reconstruct elements: '2026-03-31' + ' ' + '12:45:00'
                        raw_date = date_nodes[0].strip()  
                        raw_time = time_nodes[0].strip()
            
                        # Clean separators to match filename: 20260331T124500
                        clean_date = raw_date.replace('-', '')
                        clean_time = raw_time.replace(':', '')
            
                        timestamp_str = f"{clean_date}T{clean_time}"
                except Exception:
                    pass

            # 2. Format Timestamp to ZATCA Standard: YYYYMMDDThhmmss
            # Uses invoice date field or defaults to current time if unassigned
            inv_date = record.invoice_date or fields.Date.context_today(self)
            #timestamp_str = fields.Datetime.to_datetime(inv_date).strftime('%Y%m%dT120000') 
            
            if hasattr(record, 'create_date') and record.create_date:
                # If there's a specific live datetime stamp, use it instead of the static flat date
                timestamp_str = fields.Datetime.context_timestamp(self, record.create_date).strftime('%Y%m%dT%H%M%S')

            # 3. Format Invoice Reference Number (Remove characters illegal in safe file paths)
            invoice_num = str(record.name or 'INVOICE').replace('/', '-').replace(' ', '_')

            # Synthesize output pattern string exactly: VAT_TIMESTAMP_NUMBER
            zatca_filename = f"{seller_vat}_{timestamp_str}_{invoice_num}"
            return zatca_filename

        # Fallback to standard Odoo generation mechanisms for other documents
        return super()._get_rendering_basename(report_ref, res_ids)

    @contextmanager
    def _chatter_debugger(self, record, section_name):
        logs = [f"<b>⚙️ Started ZATCA {section_name}</b>"]
        try:
            yield logs
            logs.append("<span style='color: green;'>✅ Section compiled successfully.</span>")
        except Exception as e:
            error_trace = traceback.format_exc()
            logs.append(f"<span style='color: red;'>❌ <b>Error:</b> {str(e)}</span>")
            logs.append(f"<pre style='background: #fff5f5; border: 1px solid #ffc1c1; padding: 5px; font-size: 11px;'>{error_trace}</pre>")
            _logger.exception("ZATCA Print Exception in %s", section_name)
        finally:
            if len(logs) > 1 and hasattr(record, 'message_post'):
                full_body = f"<div style='font-family: monospace; line-height: 1.5;'>{'<br/>'.join(logs)}</div>"
                try:
                    record.message_post(body=full_body, message_type='comment')
                except Exception:
                    _logger.error("Failed writing debug log to chatter on %s", record.name)

    def _render_qweb_pdf_prepare_streams(self, report_ref, data=None, res_ids=None):
        collected_streams = super()._render_qweb_pdf_prepare_streams(report_ref, data=data, res_ids=res_ids)
        
        report = self._get_report_from_name(report_ref)
        if not report or not res_ids or report.model != 'zatca.archive.invoice':
            return collected_streams

        for archive_id in res_ids:
            archive_record = self.env['zatca.archive.invoice'].browse(archive_id)
            attachment = False
            
            with self._chatter_debugger(archive_record, "XML Extraction & QR Sync") as debug:
                attachment = self.env['ir.attachment'].search([
                    ('res_model', '=', 'zatca.archive.invoice'),
                    ('res_id', '=', archive_record.id),
                    ('mimetype', 'in', ['text/xml', 'application/xml'])
                ], limit=1)

                if not attachment and archive_record.name:
                    normalized_name = archive_record.name.replace('/', '-')
                    attachment = self.env['ir.attachment'].search([
                        ('name', 'ilike', normalized_name),
                        ('mimetype', 'in', ['text/xml', 'application/xml'])
                    ], limit=1)

                if not attachment:
                    continue

                xml_raw_bytes = attachment.raw or base64.b64decode(attachment.datas)
                parser = etree.XMLParser(recover=True, remove_blank_text=True)
                xml_root = etree.fromstring(xml_raw_bytes, parser=parser)
                
                namespaces = {
                    'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
                    'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2'
                }
                
                qr_elements = xml_root.xpath(
                    '//cac:AdditionalDocumentReference[cbc:ID="QR"]/cac:Attachment/cbc:EmbeddedDocumentBinaryObject/text()', 
                    namespaces=namespaces
                )
                
                if qr_elements:
                    qr_str = qr_elements[0].strip()
                    if hasattr(archive_record, 'l10n_sa_qr_code_str'):
                        archive_record.sudo().write({'l10n_sa_qr_code_str': qr_str})

            if not attachment:
                continue

            with self._chatter_debugger(archive_record, "PDF/A-3 Compliance Engine") as debug:
                pdf_stream = collected_streams.get(archive_id)
                pdf_writer = pdf_stream.get('writer') if pdf_stream else None
                
                is_manual_stream = False
                if not pdf_writer and pdf_stream and 'stream' in pdf_stream:
                    try:
                        raw_pdf_input = pdf_stream['stream'].getvalue()
                        pdf_reader = OdooPdfFileReader(io.BytesIO(raw_pdf_input), strict=False)
                        
                        if hasattr(pdf_reader, 'trailer') and '/Root' in pdf_reader.trailer:
                            root_dir = pdf_reader.trailer['/Root']
                            if '/Outlines' not in root_dir:
                                root_dir[('/Outlines')] = {}

                        pdf_writer = OdooPdfFileWriter()
                        pdf_writer.appendPagesFromReader(pdf_reader)
                        pdf_writer._reader = pdf_reader
                        is_manual_stream = True
                    except Exception:
                        continue

                if not pdf_writer:
                    continue

                pdf_writer.embed_odoo_attachment(attachment, subtype='application/xml')

                attachments = getattr(pdf_writer, '_attachments', [])
                if attachments:
                    last_attachment = attachments[-1]
                    if isinstance(last_attachment, tuple) and len(last_attachment) >= 3 and isinstance(last_attachment[2], dict):
                        options = dict(last_attachment[2])
                        options['relationship'] = 'Alternative'
                        attachments[-1] = (last_attachment[0], last_attachment[1], options)

                pdf_writer.is_pdfa = True

                if not getattr(pdf_writer, 'is_pdfa_converted', False):
                    try:
                        pdf_writer.convert_to_pdfa()
                    except Exception:
                        pass

                # --- EXTRACT LIVE COMPLIANCE SEGMENTS FOR FATOORA BLUEPRINT ---
                today_date = fields.Date.context_today(self).strftime('%Y-%m-%d')
                invoice_uuid = getattr(archive_record, 'zatca_uuid', '00000000-0000-0000-0000-000000000000') or '00000000-0000-0000-0000-000000000000'
                
                # Establish ZATCA structural subtypes (0100000 for Standard, 0200000 for Simplified)
                raw_status = getattr(archive_record, 'zatca_status', 'reported')
                invoice_type = "0200000" if raw_status == 'reported' else "0100000"

                # --- PRODUCTION-GRADE ZATCA SPECIFIC XMP MATRIX ---
                xmp_metadata = f"""<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  
  <rdf:Description rdf:about="" xmlns:pdfaid="http://www.aiim.org/pdfa/ns/id/">
   <pdfaid:part>3</pdfaid:part>
   <pdfaid:conformance>B</pdfaid:conformance>
  </rdf:Description>
  
  <rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/">
   <dc:title><rdf:Alt><rdf:li xml:lang="x-default">{archive_record.name}</rdf:li></rdf:Alt></dc:title>
   <dc:date><rdf:Seq><rdf:li>{today_date}</rdf:li></rdf:Seq></dc:date>
   <dc:creator><rdf:Seq><rdf:li>Odoo User Core</rdf:li></rdf:Seq></dc:creator>
  </rdf:Description>

  <rdf:Description rdf:about="" xmlns:pdfaExtension="http://www.aiim.org/pdfa/ns/extension/" xmlns:pdfaSchema="http://www.aiim.org/pdfa/ns/schema#" xmlns:pdfaProperty="http://www.aiim.org/pdfa/ns/property#">
   <pdfaExtension:schemas>
    <rdf:Bag>
     <rdf:li rdf:parseType="Resource">
      <pdfaSchema:schema>ZATCA Electronic Invoice Properties</pdfaSchema:schema>
      <pdfaSchema:namespaceURI>http://zatca.gov.sa/invoice/pdfa/v1/</pdfaSchema:namespaceURI>
      <pdfaSchema:prefix>zatca</pdfaSchema:prefix>
      <pdfaSchema:property>
       <rdf:Seq>
        <rdf:li rdf:parseType="Resource">
         <pdfaProperty:name>InvoiceType</pdfaProperty:name>
         <pdfaProperty:valueType>Text</pdfaProperty:valueType>
         <pdfaProperty:category>external</pdfaProperty:category>
         <pdfaProperty:description>ZATCA Subtype Specification Identification</pdfaProperty:description>
        </rdf:li>
        <rdf:li rdf:parseType="Resource">
         <pdfaProperty:name>UUID</pdfaProperty:name>
         <pdfaProperty:valueType>Text</pdfaProperty:valueType>
         <pdfaProperty:category>external</pdfaProperty:category>
         <pdfaProperty:description>Cryptographic Unique Universal Identifier</pdfaProperty:description>
        </rdf:li>
       </rdf:Seq>
      </pdfaSchema:property>
     </rdf:li>
    </rdf:Bag>
   </pdfaExtension:schemas>
  </rdf:Description>

  <rdf:Description rdf:about="" xmlns:zatca="http://zatca.gov.sa/invoice/pdfa/v1/">
   <zatca:InvoiceType>{invoice_type}</zatca:InvoiceType>
   <zatca:UUID>{invoice_uuid}</zatca:UUID>
  </rdf:Description>

 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>"""
                pdf_writer.add_file_metadata(xmp_metadata.encode('utf-8'))

                if is_manual_stream:
                    output_stream = io.BytesIO()
                    pdf_writer.write(output_stream)
                    pdf_stream['stream'] = output_stream

        return collected_streams
