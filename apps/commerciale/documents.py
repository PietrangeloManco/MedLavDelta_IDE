from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from xml.dom import minidom
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from svglib.svglib import svg2rlg


FATTURA_PA_NAMESPACE = 'http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2'
XMLDSIG_NAMESPACE = 'http://www.w3.org/2000/09/xmldsig#'
XSI_NAMESPACE = 'http://www.w3.org/2001/XMLSchema-instance'
FATTURA_PA_SCHEMA_LOCATION = (
    'http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2 '
    'http://www.fatturapa.gov.it/export/fatturazione/sdi/fatturapa/v1.2/'
    'Schema_del_file_xml_FatturaPA_versione_1.2.xsd'
)


@dataclass(frozen=True)
class InvoiceIssuer:
    display_name: str
    legal_name: str
    vat_code: str
    fiscal_code: str
    rea: str
    pec: str
    address: str
    cap: str
    city: str
    province: str
    nation: str = 'IT'
    phone: str = '0824 363764'
    fax: str = '0824 364092'
    tax_regime: str = 'RF01'


ISSUER = InvoiceIssuer(
    display_name='Centro Delta IDAB S.r.l.',
    legal_name='CENTRO MEDICO DELTA IDAB - ISTITUTO DI DIAGNOSTICA AVANZATA E DI BIOTECNOLOGIE S.R.L.',
    vat_code='00269500625',
    fiscal_code='00269500625',
    rea='BN-56843',
    pec='centrodelta@arubapec.it',
    address='Piazza San Giuseppe Moscati 8 KM 254+900',
    cap='82030',
    city='Apollosa',
    province='BN',
)


def _decimal_string(value: Decimal | int | float | str) -> str:
    return f'{Decimal(value).quantize(Decimal("0.01")):.2f}'


def _currency_string(value: Decimal | int | float | str) -> str:
    normalized = _decimal_string(value)
    integer_part, decimals = normalized.split('.')
    integer_part = f'{int(integer_part):,}'.replace(',', '.')
    return f'EUR {integer_part},{decimals}'


def _date_string(value) -> str:
    return value.strftime('%d/%m/%Y') if value else '-'


def _xml_date_string(value) -> str:
    return value.strftime('%Y-%m-%d') if value else ''


def _compact_text(value: str) -> str:
    return ' '.join((value or '').split())


def _paragraph_text(value: str) -> str:
    return escape((value or '').strip()).replace('\n', '<br/>')


def _buyer_data(fattura):
    azienda = fattura.azienda
    sede = azienda.sedi.order_by('id').first()
    return {
        'denominazione': azienda.ragione_sociale,
        'partita_iva': (azienda.partita_iva or '').strip(),
        'codice_fiscale': (azienda.codice_fiscale or '').strip(),
        'codice_destinatario': (azienda.codice_univoco or '0000000').strip().upper(),
        'pec': (azienda.pec or '').strip(),
        'indirizzo': (
            fattura.indirizzo_fatturazione
            or (sede.indirizzo if sede else '')
            or 'Indirizzo da completare'
        ).strip(),
        'cap': (
            fattura.cap_fatturazione
            or (sede.cap if sede else '')
            or '00000'
        ).strip(),
        'comune': (
            fattura.comune_fatturazione
            or (sede.citta if sede else '')
            or 'ND'
        ).strip(),
        'provincia': (
            fattura.provincia_fatturazione
            or (sede.provincia if sede else '')
            or 'EE'
        ).strip().upper(),
        'nazione': 'IT',
    }


def _payment_conditions_code(fattura) -> str:
    modalita = (fattura.modalita_pagamento or '').lower()
    return 'TP01' if 'rate' in modalita else 'TP02'


def _payment_mode_code(fattura) -> str:
    modalita = (fattura.modalita_pagamento or '').lower()
    if 'bonifico' in modalita:
        return 'MP05'
    if 'contanti' in modalita:
        return 'MP01'
    if 'assegno' in modalita:
        return 'MP02'
    if 'rid' in modalita or 'sepa' in modalita:
        return 'MP19'
    return 'MP05'


def _vat_exigibility_code(fattura) -> str:
    value = (fattura.esigibilita_iva or '').lower()
    if 'scissione' in value or 'split' in value:
        return 'S'
    if 'differita' in value:
        return 'D'
    return 'I'


def _invoice_progressive_code(fattura) -> str:
    seed = fattura.pk or fattura.numero_progressivo or 0
    return f'{seed:010d}'


def invoice_pdf_filename(fattura) -> str:
    return f'Fattura_{fattura.numero_progressivo or "bozza"}_{fattura.anno_fattura}.pdf'


def invoice_xml_filename(fattura) -> str:
    return f'IT{ISSUER.vat_code}_{_invoice_progressive_code(fattura)}.xml'


def build_invoice_xml_bytes(fattura) -> bytes:
    buyer = _buyer_data(fattura)

    ET.register_namespace('p', FATTURA_PA_NAMESPACE)
    ET.register_namespace('ds', XMLDSIG_NAMESPACE)
    ET.register_namespace('xsi', XSI_NAMESPACE)

    root = ET.Element(
        ET.QName(FATTURA_PA_NAMESPACE, 'FatturaElettronica'),
        attrib={
            'versione': 'FPR12',
            ET.QName(XSI_NAMESPACE, 'schemaLocation'): FATTURA_PA_SCHEMA_LOCATION,
        },
    )
    header = ET.SubElement(root, 'FatturaElettronicaHeader')
    dati_trasmissione = ET.SubElement(header, 'DatiTrasmissione')
    id_trasmittente = ET.SubElement(dati_trasmissione, 'IdTrasmittente')
    ET.SubElement(id_trasmittente, 'IdPaese').text = ISSUER.nation
    ET.SubElement(id_trasmittente, 'IdCodice').text = ISSUER.vat_code
    ET.SubElement(dati_trasmissione, 'ProgressivoInvio').text = _invoice_progressive_code(fattura)
    ET.SubElement(dati_trasmissione, 'FormatoTrasmissione').text = 'FPR12'
    ET.SubElement(dati_trasmissione, 'CodiceDestinatario').text = buyer['codice_destinatario']
    if buyer['codice_destinatario'] == '0000000' and buyer['pec']:
        ET.SubElement(dati_trasmissione, 'PECDestinatario').text = buyer['pec']

    cedente = ET.SubElement(header, 'CedentePrestatore')
    dati_anagrafici = ET.SubElement(cedente, 'DatiAnagrafici')
    id_fiscale_iva = ET.SubElement(dati_anagrafici, 'IdFiscaleIVA')
    ET.SubElement(id_fiscale_iva, 'IdPaese').text = ISSUER.nation
    ET.SubElement(id_fiscale_iva, 'IdCodice').text = ISSUER.vat_code
    ET.SubElement(dati_anagrafici, 'CodiceFiscale').text = ISSUER.fiscal_code
    anagrafica = ET.SubElement(dati_anagrafici, 'Anagrafica')
    ET.SubElement(anagrafica, 'Denominazione').text = ISSUER.legal_name
    ET.SubElement(dati_anagrafici, 'RegimeFiscale').text = ISSUER.tax_regime
    sede = ET.SubElement(cedente, 'Sede')
    ET.SubElement(sede, 'Indirizzo').text = ISSUER.address
    ET.SubElement(sede, 'CAP').text = ISSUER.cap
    ET.SubElement(sede, 'Comune').text = ISSUER.city
    ET.SubElement(sede, 'Provincia').text = ISSUER.province
    ET.SubElement(sede, 'Nazione').text = ISSUER.nation

    cessionario = ET.SubElement(header, 'CessionarioCommittente')
    dati_cliente = ET.SubElement(cessionario, 'DatiAnagrafici')
    if buyer['partita_iva']:
        buyer_iva = ET.SubElement(dati_cliente, 'IdFiscaleIVA')
        ET.SubElement(buyer_iva, 'IdPaese').text = buyer['nazione']
        ET.SubElement(buyer_iva, 'IdCodice').text = buyer['partita_iva']
    if buyer['codice_fiscale']:
        ET.SubElement(dati_cliente, 'CodiceFiscale').text = buyer['codice_fiscale']
    buyer_anagrafica = ET.SubElement(dati_cliente, 'Anagrafica')
    ET.SubElement(buyer_anagrafica, 'Denominazione').text = buyer['denominazione']
    buyer_sede = ET.SubElement(cessionario, 'Sede')
    ET.SubElement(buyer_sede, 'Indirizzo').text = buyer['indirizzo']
    ET.SubElement(buyer_sede, 'CAP').text = buyer['cap']
    ET.SubElement(buyer_sede, 'Comune').text = buyer['comune']
    ET.SubElement(buyer_sede, 'Provincia').text = buyer['provincia']
    ET.SubElement(buyer_sede, 'Nazione').text = buyer['nazione']

    body = ET.SubElement(root, 'FatturaElettronicaBody')
    dati_generali = ET.SubElement(body, 'DatiGenerali')
    documento = ET.SubElement(dati_generali, 'DatiGeneraliDocumento')
    ET.SubElement(documento, 'TipoDocumento').text = 'TD01'
    ET.SubElement(documento, 'Divisa').text = 'EUR'
    ET.SubElement(documento, 'Data').text = _xml_date_string(fattura.data_fattura)
    ET.SubElement(documento, 'Numero').text = fattura.numero_documento
    sconto_documento = ET.SubElement(documento, 'ScontoMaggiorazione')
    ET.SubElement(sconto_documento, 'Tipo').text = 'SC'
    ET.SubElement(sconto_documento, 'Importo').text = _decimal_string(Decimal('0.00'))
    ET.SubElement(documento, 'ImportoTotaleDocumento').text = _decimal_string(fattura.totale_complessivo)
    if fattura.causale:
        ET.SubElement(documento, 'Causale').text = _compact_text(fattura.causale)

    dati_beni_servizi = ET.SubElement(body, 'DatiBeniServizi')
    active_lines = [voce for voce in fattura.voci.order_by('ordine', 'id') if voce.descrizione]
    for index, voce in enumerate(active_lines, start=1):
        linea = ET.SubElement(dati_beni_servizi, 'DettaglioLinee')
        ET.SubElement(linea, 'NumeroLinea').text = str(index)
        ET.SubElement(linea, 'Descrizione').text = _compact_text(voce.descrizione)
        ET.SubElement(linea, 'Quantita').text = _decimal_string(voce.quantita)
        ET.SubElement(linea, 'UnitaMisura').text = 'Num.'
        ET.SubElement(linea, 'PrezzoUnitario').text = _decimal_string(voce.costo_unitario)
        sconto = ET.SubElement(linea, 'ScontoMaggiorazione')
        ET.SubElement(sconto, 'Tipo').text = 'SC'
        ET.SubElement(sconto, 'Percentuale').text = _decimal_string(voce.sconto_percentuale)
        ET.SubElement(linea, 'PrezzoTotale').text = _decimal_string(voce.importo_totale)
        ET.SubElement(linea, 'AliquotaIVA').text = _decimal_string(fattura.aliquota_iva)

    riepilogo = ET.SubElement(dati_beni_servizi, 'DatiRiepilogo')
    ET.SubElement(riepilogo, 'AliquotaIVA').text = _decimal_string(fattura.aliquota_iva)
    ET.SubElement(riepilogo, 'ImponibileImporto').text = _decimal_string(fattura.totale_imponibile)
    ET.SubElement(riepilogo, 'Imposta').text = _decimal_string(fattura.totale_iva)
    ET.SubElement(riepilogo, 'EsigibilitaIVA').text = _vat_exigibility_code(fattura)

    dati_pagamento = ET.SubElement(body, 'DatiPagamento')
    ET.SubElement(dati_pagamento, 'CondizioniPagamento').text = _payment_conditions_code(fattura)
    dettaglio_pagamento = ET.SubElement(dati_pagamento, 'DettaglioPagamento')
    ET.SubElement(dettaglio_pagamento, 'ModalitaPagamento').text = _payment_mode_code(fattura)
    if fattura.scadenza:
        ET.SubElement(dettaglio_pagamento, 'DataScadenzaPagamento').text = _xml_date_string(
            fattura.scadenza
        )
    ET.SubElement(dettaglio_pagamento, 'ImportoPagamento').text = _decimal_string(
        fattura.totale_complessivo
    )
    if fattura.banca_appoggio:
        ET.SubElement(dettaglio_pagamento, 'IstitutoFinanziario').text = fattura.banca_appoggio

    pretty_xml = minidom.parseString(ET.tostring(root, encoding='utf-8')).toprettyxml(
        indent='  ',
        encoding='UTF-8',
    )
    return pretty_xml


def build_invoice_pdf_bytes(fattura) -> bytes:
    buyer = _buyer_data(fattura)
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name='InvoiceBrand',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=17,
            leading=19,
            textColor=colors.HexColor('#1c256a'),
        )
    )
    styles.add(
        ParagraphStyle(
            name='InvoiceSmall',
            parent=styles['BodyText'],
            fontSize=8,
            leading=10,
        )
    )
    styles.add(
        ParagraphStyle(
            name='InvoiceCell',
            parent=styles['BodyText'],
            fontSize=8,
            leading=10,
        )
    )
    styles.add(
        ParagraphStyle(
            name='InvoiceRight',
            parent=styles['BodyText'],
            fontSize=8,
            leading=10,
            alignment=TA_RIGHT,
        )
    )

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=24 * mm,
    )

    def _brand_logo():
        logo_path = Path(settings.BASE_DIR) / 'static' / 'Logo_oriz.svg'
        try:
            drawing = svg2rlg(str(logo_path))
        except Exception:
            drawing = None
        if not drawing:
            return Paragraph(
                (
                    f'<b>{escape(ISSUER.display_name.upper())}</b>'
                    '<br/><font size="8">Medicina del Lavoro</font>'
                ),
                styles['InvoiceBrand'],
            )
        max_width = 48 * mm
        if drawing.width:
            scale = min(max_width / drawing.width, 1)
            drawing.scale(scale, scale)
            drawing.width *= scale
            drawing.height *= scale
        return drawing

    buyer_lines = [
        buyer['denominazione'],
        buyer['indirizzo'],
        f"{buyer['cap']} {buyer['comune']} {buyer['provincia']}".strip(),
    ]
    buyer_box = Table(
        [[Paragraph('<br/>'.join(_paragraph_text(line) for line in buyer_lines if line), styles['InvoiceCell'])]],
        colWidths=[90 * mm],
    )
    buyer_box.setStyle(
        TableStyle(
            [
                ('BOX', (0, 0), (-1, -1), 0.7, colors.HexColor('#cbd5e1')),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]
        )
    )

    header_table = Table(
        [
            [
                _brand_logo(),
                Table(
                    [[Paragraph('Spett.Le', styles['InvoiceCell']), buyer_box]],
                    colWidths=[18 * mm, 90 * mm],
                ),
            ]
        ],
        colWidths=[70 * mm, 108 * mm],
    )
    header_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))

    info_table = Table(
        [
            [
                Paragraph(
                    f'<b>P.IVA/Codice Fiscale</b> '
                    f'{escape(buyer["partita_iva"] or buyer["codice_fiscale"] or "-")}',
                    styles['InvoiceCell'],
                ),
                Paragraph(
                    f'<b>Modalità di pagamento</b> {escape(fattura.modalita_pagamento or "-")}',
                    styles['InvoiceCell'],
                ),
            ],
            [
                Paragraph(
                    f'<b>G.D.D.</b><br/>{escape(fattura.gdd or "-")}',
                    styles['InvoiceCell'],
                ),
                Paragraph(
                    f'<b>Banca d\'appoggio</b><br/>{escape(fattura.banca_appoggio or "-")}',
                    styles['InvoiceCell'],
                ),
            ],
            [
                Paragraph(
                    f'<b>Scadenza pagamento</b><br/>{_date_string(fattura.scadenza)}',
                    styles['InvoiceCell'],
                ),
                Paragraph(
                    f'<b>Codice destinatario</b><br/>{escape(buyer["codice_destinatario"] or "-")}',
                    styles['InvoiceCell'],
                ),
            ],
        ],
        colWidths=[86 * mm, 92 * mm],
    )
    info_table.setStyle(
        TableStyle(
            [
                ('GRID', (0, 0), (-1, -1), 0.7, colors.HexColor('#cbd5e1')),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]
        )
    )

    line_rows = [
        [
            Paragraph('<b>Descrizione Prestazioni Effettuate</b>', styles['InvoiceCell']),
            Paragraph('<b>Q.tà</b>', styles['InvoiceRight']),
            Paragraph('<b>Costo</b>', styles['InvoiceRight']),
            Paragraph('<b>Sconto (%)</b>', styles['InvoiceRight']),
            Paragraph('<b>Importo</b>', styles['InvoiceRight']),
        ]
    ]
    for voce in fattura.voci.order_by('ordine', 'id'):
        line_rows.append(
            [
                Paragraph(_paragraph_text(voce.descrizione or '-'), styles['InvoiceCell']),
                Paragraph(_decimal_string(voce.quantita), styles['InvoiceRight']),
                Paragraph(_currency_string(voce.costo_unitario), styles['InvoiceRight']),
                Paragraph(_decimal_string(voce.sconto_percentuale), styles['InvoiceRight']),
                Paragraph(_currency_string(voce.importo_totale), styles['InvoiceRight']),
            ]
        )

    detail_table = Table(
        line_rows,
        colWidths=[92 * mm, 16 * mm, 24 * mm, 22 * mm, 24 * mm],
        repeatRows=1,
    )
    detail_table.setStyle(
        TableStyle(
            [
                ('GRID', (0, 0), (-1, -1), 0.6, colors.HexColor('#cbd5e1')),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f8fafc')),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 5),
                ('RIGHTPADDING', (0, 0), (-1, -1), 5),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ]
        )
    )

    summary_table = Table(
        [
            ['Totale Prestazioni', _currency_string(fattura.totale_imponibile)],
            ['Imponibile ai fini IVA', _currency_string(fattura.totale_imponibile)],
            [f'IVA {_decimal_string(fattura.aliquota_iva)}%', _currency_string(fattura.totale_iva)],
            ['Totale Fattura', _currency_string(fattura.totale_complessivo)],
            ['Netto a pagare', _currency_string(fattura.totale_complessivo)],
        ],
        colWidths=[48 * mm, 30 * mm],
        hAlign='RIGHT',
    )
    summary_table.setStyle(
        TableStyle(
            [
                ('GRID', (0, 0), (-1, -1), 0.6, colors.HexColor('#cbd5e1')),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
                ('LEFTPADDING', (0, 0), (-1, -1), 5),
                ('RIGHTPADDING', (0, 0), (-1, -1), 5),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ]
        )
    )

    story = [
        header_table,
        Spacer(1, 10),
        Table(
            [[Paragraph(f'<b>N. Fattura {fattura.numero_documento} del {_date_string(fattura.data_fattura)}</b>', styles['InvoiceRight'])]],
            colWidths=[178 * mm],
        ),
        Spacer(1, 6),
        info_table,
        Spacer(1, 8),
        detail_table,
    ]

    footer_lines = [f'Esigibilità IVA: {fattura.esigibilita_iva or "-"}']
    if fattura.categoria_merceologica_display:
        footer_lines.append(f'Categoria merceologica: {fattura.categoria_merceologica_display}')
    if fattura.causale:
        footer_lines.append(f'Causale: {fattura.causale}')

    for line in footer_lines:
        story.extend([Spacer(1, 4), Paragraph(line, styles['InvoiceSmall'])])

    story.extend(
        [
            Spacer(1, 8),
            summary_table,
            Spacer(1, 8),
            Paragraph(
                'Interessi di mora per ritardato pagamento ai sensi del D.Lgs 192 del 09.11.2012',
                styles['InvoiceSmall'],
            ),
        ]
    )

    def _draw_footer(canvas, document):
        canvas.saveState()
        canvas.setFont('Helvetica', 7)
        canvas.setFillColor(colors.HexColor('#1c256a'))
        footer_y = 16 * mm
        canvas.drawString(
            document.leftMargin,
            footer_y + 8,
            ISSUER.display_name,
        )
        canvas.setFillColor(colors.black)
        canvas.drawString(
            document.leftMargin,
            footer_y,
            (
                f'Sede legale {ISSUER.address} - {ISSUER.cap} {ISSUER.city} {ISSUER.province} | '
                f'P.I. {ISSUER.vat_code} | REA {ISSUER.rea} | PEC {ISSUER.pec}'
            ),
        )
        canvas.drawRightString(
            A4[0] - document.rightMargin,
            footer_y,
            f'Pagina {canvas.getPageNumber()}',
        )
        canvas.restoreState()

    doc.build(story, onFirstPage=_draw_footer, onLaterPages=_draw_footer)
    return buffer.getvalue()
