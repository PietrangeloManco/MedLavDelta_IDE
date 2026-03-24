from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.aziende.models import Azienda

from .models import Fattura, Preventivo


class CommercialeAdminFlowTests(TestCase):
    def setUp(self):
        self.admin_user = CustomUser.objects.create_user(
            email='admin@example.com',
            password='admin-pass-123',
            role=CustomUser.ADMIN,
            is_staff=True,
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
            email_contatto='contatti@example.com',
            condizioni_pagamento_riservate='Bonifico 30 giorni data fattura.',
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
            'indirizzo_fatturazione': 'Via Roma 1',
            'condizioni_pagamento_riservate': '',
            'modalita_pagamento': 'Bonifico',
            'aliquota_iva': '22.00',
            'esente_iva': '',
            'esigibilita_iva': 'IVA ad esigibilita immediata',
            'gdd': '30',
            'fine_mese': '',
            'scadenza': '2026-04-23',
            'banca_appoggio': 'Banca Test',
            'note': '',
            'inviata_il': '2026-03-24',
            'voci-TOTAL_FORMS': '1',
            'voci-INITIAL_FORMS': '0',
            'voci-MIN_NUM_FORMS': '0',
            'voci-MAX_NUM_FORMS': '1000',
            'voci-0-descrizione': 'Analisi laboratorio',
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

    def test_fattura_list_shows_sample_acceptance_date(self):
        response = self.client.post(reverse('admin_fattura_nuova'), data=self._fattura_payload())

        self.assertRedirects(response, reverse('admin_fatture'))

        fattura = Fattura.objects.get()
        self.assertEqual(fattura.condizioni_pagamento_riservate, self.azienda.condizioni_pagamento_riservate)

        list_response = self.client.get(reverse('admin_fatture'))
        self.assertContains(list_response, '20/03/2026')
        self.assertContains(list_response, '24/03/2026')

    def test_fattura_create_page_renders(self):
        response = self.client.get(reverse('admin_fattura_nuova'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Data Accettazione Campione')
