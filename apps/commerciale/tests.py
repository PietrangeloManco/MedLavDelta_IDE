from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.aziende.models import Azienda, Sede

from .models import Fattura, Preventivo


class CommercialeAdminFlowTests(TestCase):
    def setUp(self):
        self.admin_user = CustomUser.objects.create_user(
            email='admin@example.com',
            password='admin-pass-123',
            role=CustomUser.ADMIN,
            is_staff=True,
            is_superuser=True,
        )
        self.azienda_user = CustomUser.objects.create_user(
            email='azienda@example.com',
            password='azienda-pass-123',
            role=CustomUser.AZIENDA,
        )
        self.azienda = Azienda.objects.create(
            user=self.azienda_user,
            ragione_sociale='Azienda Test SRL',
            codice_univoco='ABC1234',
            pec='azienda@pec.example.com',
            referente_azienda='Mario Rossi',
            codice_fiscale='RSSMRA80A01H501Z',
            partita_iva='12345678901',
            email_contatto='contatti@example.com',
            condizioni_pagamento_riservate='Bonifico 30 giorni data fattura.',
        )
        self.sede = Sede.objects.create(
            azienda=self.azienda,
            nome='Sede legale',
            indirizzo='Via Roma 1',
            citta='Benevento',
            cap='82100',
            provincia='BN',
        )
        self.client.force_login(self.admin_user)

    def _preventivo_payload(self):
        return {
            'numero_preventivo': '1',
            'data_preventivo': '2026-03-24',
            'azienda': str(self.azienda.pk),
            'oggetto': 'Sorveglianza sanitaria annuale',
            'descrizione_oggetto': 'Preventivo di prova',
            'note': '',
            'riferimento_commerciale': 'Ufficio commerciale',
            'assistente_tecnico': 'Tecnico 1',
            'giorni_lavorativi': '10',
            'durata_offerta': '2026-04-30',
            'condizioni_pagamento_riservate': '',
            'aliquota_iva': '22.00',
            'voci-TOTAL_FORMS': '1',
            'voci-INITIAL_FORMS': '0',
            'voci-MIN_NUM_FORMS': '0',
            'voci-MAX_NUM_FORMS': '1000',
            'voci-0-descrizione': 'Visita medica',
            'voci-0-quantita': '2',
            'voci-0-costo_unitario': '50.00',
            'voci-0-sconto_percentuale': '0',
            'voci-0-ordine': '0',
        }

    def _fattura_payload(self):
        return {
            'anno_fattura': '2026',
            'prefisso_numero': 'FPR',
            'numero_progressivo': '1',
            'data_fattura': '2026-03-24',
            'data_accettazione_campione': '2026-03-20',
            'azienda': str(self.azienda.pk),
            'categoria_merceologica': 'ANALISI CHIMICO FISICHE E MICROBIOLOGICHE',
            'indirizzo_fatturazione': 'Via Roma 1',
            'cap_fatturazione': '82100',
            'comune_fatturazione': 'Benevento',
            'provincia_fatturazione': 'BN',
            'condizioni_pagamento_riservate': '',
            'modalita_pagamento': 'pagamento completo - bonifico',
            'aliquota_iva': '22.00',
            'esente_iva': '',
            'esigibilita_iva': 'IVA ad esigibilita immediata',
            'gdd': '60gg G.G.D.F',
            'fine_mese': '',
            'scadenza': '2026-04-23',
            'banca_appoggio': 'Banca Test',
            'causale': 'RIF. PREVENTIVO N. 109 DEL 18/05/2021',
            'note': 'Nota interna di test',
            'inviata_il': '2026-03-24',
            'data_incasso': '2026-03-28',
            'voci-TOTAL_FORMS': '1',
            'voci-INITIAL_FORMS': '0',
            'voci-MIN_NUM_FORMS': '0',
            'voci-MAX_NUM_FORMS': '1000',
            'voci-0-descrizione': (
                'N. Campione: 08164_2025 - Categoria Merceologica: '
                'ANALISI CHIMICO FISICHE E MICROBIOLOGICHE - Prodotto Dichiarato: MATERIALI'
            ),
            'voci-0-quantita': '1',
            'voci-0-costo_unitario': '100.00',
            'voci-0-sconto_percentuale': '0',
            'voci-0-ordine': '0',
        }

    def test_preventivo_creation_uses_company_reserved_payment_terms(self):
        response = self.client.post(reverse('admin_preventivo_nuovo'), data=self._preventivo_payload())

        self.assertRedirects(response, reverse('admin_preventivi'))

        preventivo = Preventivo.objects.get()
        self.assertEqual(preventivo.condizioni_pagamento_riservate, self.azienda.condizioni_pagamento_riservate)
        self.assertEqual(preventivo.totale_imponibile, Decimal('100.00'))
        self.assertEqual(preventivo.totale_complessivo, Decimal('122.00'))

    def test_preventivo_create_page_renders(self):
        response = self.client.get(reverse('admin_preventivo_nuovo'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Condizioni Pagamento Riservate')

    def test_preventivi_list_supports_search_and_sort(self):
        self.client.post(reverse('admin_preventivo_nuovo'), data=self._preventivo_payload())
        second_payload = self._preventivo_payload()
        second_payload.update({
            'numero_preventivo': '2',
            'oggetto': 'Formazione sicurezza',
        })
        self.client.post(reverse('admin_preventivo_nuovo'), data=second_payload)

        search_response = self.client.get(reverse('admin_preventivi'), {'q': 'Formazione'})
        sort_response = self.client.get(reverse('admin_preventivi'), {'sort': 'numero', 'dir': 'desc'})
        sort_html = sort_response.content.decode()

        self.assertContains(search_response, 'Formazione sicurezza')
        self.assertNotContains(search_response, 'Sorveglianza sanitaria annuale')
        self.assertLess(sort_html.find('00000002'), sort_html.find('00000001'))

    def test_fattura_list_shows_operational_columns_and_actions(self):
        response = self.client.post(reverse('admin_fattura_nuova'), data=self._fattura_payload())

        self.assertRedirects(response, reverse('admin_fatture'))

        fattura = Fattura.objects.get()
        self.assertEqual(fattura.condizioni_pagamento_riservate, self.azienda.condizioni_pagamento_riservate)

        list_response = self.client.get(reverse('admin_fatture'))
        self.assertContains(list_response, 'FPR 1')
        self.assertContains(list_response, '24/03/2026')
        self.assertContains(list_response, '28/03/2026')
        self.assertContains(list_response, 'ANALISI CHIMICO FISICHE E MICROBIOLOGICHE')
        self.assertContains(
            list_response,
            f'<a href="{reverse("admin_fattura_modifica", args=[fattura.pk])}" class="invoice-number-link">FPR 1</a>',
            html=True,
        )
        self.assertContains(list_response, reverse('admin_fattura_pdf', args=[fattura.pk]))
        self.assertContains(list_response, 'Nota interna di test')

    def test_fattura_create_page_renders(self):
        response = self.client.get(reverse('admin_fattura_nuova'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Categoria Merceologica')

    def test_fatture_list_supports_search_and_sort(self):
        self.client.post(reverse('admin_fattura_nuova'), data=self._fattura_payload())
        second_payload = self._fattura_payload()
        second_payload.update({
            'numero_progressivo': '2',
            'categoria_merceologica': 'HACCP',
            'note': 'Seconda fattura',
            'voci-0-descrizione': 'Categoria Merceologica: HACCP - Prodotto Dichiarato: TEST',
        })
        self.client.post(reverse('admin_fattura_nuova'), data=second_payload)

        search_response = self.client.get(reverse('admin_fatture'), {'q': 'Seconda fattura'})
        sort_response = self.client.get(reverse('admin_fatture'), {'sort': 'numero', 'dir': 'desc'})
        sort_html = sort_response.content.decode()

        self.assertContains(search_response, 'Seconda fattura')
        self.assertNotContains(search_response, 'Nota interna di test')
        self.assertLess(sort_html.find('FPR 2'), sort_html.find('FPR 1'))

    def test_company_payment_api_includes_billing_defaults(self):
        response = self.client.get(
            reverse('admin_api_azienda_condizioni_pagamento', args=[self.azienda.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {
                'condizioni_pagamento_riservate': 'Bonifico 30 giorni data fattura.',
                'indirizzo_fatturazione': 'Via Roma 1',
                'cap_fatturazione': '82100',
                'comune_fatturazione': 'Benevento',
                'provincia_fatturazione': 'BN',
            },
        )

    def test_fattura_pdf_view_returns_inline_pdf(self):
        self.client.post(reverse('admin_fattura_nuova'), data=self._fattura_payload())
        fattura = Fattura.objects.get()

        response = self.client.get(reverse('admin_fattura_pdf', args=[fattura.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('inline;', response['Content-Disposition'])
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_fattura_xml_download_uses_centro_delta_issuer(self):
        self.client.post(reverse('admin_fattura_nuova'), data=self._fattura_payload())
        fattura = Fattura.objects.get()

        response = self.client.get(reverse('admin_fattura_xml', args=[fattura.pk]))
        content = response.content.decode('utf-8')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/xml')
        self.assertIn('attachment;', response['Content-Disposition'])
        self.assertIn('CENTRO MEDICO DELTA IDAB', content)
        self.assertIn('00269500625', content)
        self.assertNotIn('TECNO BIOS', content)
        self.assertIn('Azienda Test SRL', content)
        self.assertIn('Via Roma 1', content)
        self.assertIn('FPR 1', content)

    def test_fattura_edit_page_shows_xml_and_pdf_actions(self):
        self.client.post(reverse('admin_fattura_nuova'), data=self._fattura_payload())
        fattura = Fattura.objects.get()

        response = self.client.get(reverse('admin_fattura_modifica', args=[fattura.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('admin_fattura_xml', args=[fattura.pk]))
        self.assertContains(response, reverse('admin_fattura_pdf', args=[fattura.pk]))
