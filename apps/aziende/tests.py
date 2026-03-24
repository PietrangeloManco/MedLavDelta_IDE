from datetime import date
from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import CustomUser

from .admin import AziendaAdminForm, LavoratoreAdminForm
from .forms import CreaAziendaForm
from .models import Azienda, Lavoratore
from .validators import (
    COMPANY_DOCUMENT_MAX_UPLOAD_SIZE,
    COMPANY_LOGO_MAX_UPLOAD_SIZE,
)


class CreaAziendaFlowTests(TestCase):
    def setUp(self):
        self.media_dir = TemporaryDirectory()
        self.media_override = override_settings(MEDIA_ROOT=self.media_dir.name)
        self.media_override.enable()

        self.admin_user = CustomUser.objects.create_user(
            email='admin@example.com',
            password='admin-pass-123',
            role=CustomUser.ADMIN,
            is_staff=True,
        )

    def tearDown(self):
        self.media_override.disable()
        self.media_dir.cleanup()

    def build_valid_data(self):
        return {
            'email': 'azienda@example.com',
            'password': 'azienda-pass-123',
            'ragione_sociale': 'Azienda Test SRL',
            'codice_univoco': 'ab12cd7',
            'pec': 'azienda@pec.example.com',
            'referente_azienda': 'Mario Rossi',
            'codice_fiscale': 'RSSMRA80A01H501Z',
            'partita_iva': '12345678901',
            'email_contatto': 'contatti@example.com',
            'telefono': '0123456789',
            'condizioni_pagamento_riservate': 'Pagamento completo entro 30 giorni data fattura.',
            'varie_note': 'Note azienda',
        }

    def build_valid_files(self):
        return {
            'logo_azienda': SimpleUploadedFile(
                'logo.svg',
                b'<svg xmlns="http://www.w3.org/2000/svg"></svg>',
                content_type='image/svg+xml',
            ),
            'protocollo_sanitario': SimpleUploadedFile(
                'protocollo.pdf',
                b'%PDF-1.4 protocollo',
                content_type='application/pdf',
            ),
            'nomina_medico': SimpleUploadedFile(
                'nomina.docx',
                b'PK\x03\x04 nomina',
                content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            ),
            'verbali_sopralluogo': SimpleUploadedFile(
                'verbali.pdf',
                b'%PDF-1.4 verbali',
                content_type='application/pdf',
            ),
            'varie_documento': SimpleUploadedFile(
                'varie.pdf',
                b'%PDF-1.4 varie',
                content_type='application/pdf',
            ),
        }

    def create_existing_company(self):
        user = CustomUser.objects.create_user(
            email='azienda-form@example.com',
            password='azienda-form-pass',
            role=CustomUser.AZIENDA,
        )
        return Azienda.objects.create(
            user=user,
            ragione_sociale='Azienda Form SRL',
            codice_univoco='ZX12CV3',
            logo_azienda=SimpleUploadedFile(
                'logo-form.svg',
                b'<svg xmlns="http://www.w3.org/2000/svg"></svg>',
                content_type='image/svg+xml',
            ),
            pec='azienda-form@pec.example.com',
            referente_azienda='Giulia Bianchi',
            codice_fiscale='GLIBNC80A01H501Z',
            partita_iva='10987654321',
            email_contatto='form@example.com',
            telefono='0987654321',
            condizioni_pagamento_riservate='Pagamento entro 15 giorni.',
            protocollo_sanitario=SimpleUploadedFile(
                'protocollo-form.pdf',
                b'%PDF-1.4 protocollo form',
                content_type='application/pdf',
            ),
        )

    def test_form_requires_new_company_profile_fields(self):
        data = self.build_valid_data()
        files = self.build_valid_files()

        data.pop('codice_univoco')
        data.pop('pec')
        data.pop('referente_azienda')
        data.pop('condizioni_pagamento_riservate')
        files.pop('logo_azienda')

        form = CreaAziendaForm(data=data, files=files)

        self.assertFalse(form.is_valid())
        self.assertIn('codice_univoco', form.errors)
        self.assertIn('pec', form.errors)
        self.assertIn('referente_azienda', form.errors)
        self.assertIn('condizioni_pagamento_riservate', form.errors)
        self.assertIn('logo_azienda', form.errors)

    def test_form_rejects_oversized_logo_and_documents(self):
        data = self.build_valid_data()
        files = self.build_valid_files()
        files['logo_azienda'] = SimpleUploadedFile(
            'logo.png',
            b'a' * (COMPANY_LOGO_MAX_UPLOAD_SIZE + 1),
            content_type='image/png',
        )

        logo_form = CreaAziendaForm(data=data, files=files)

        self.assertFalse(logo_form.is_valid())
        self.assertIn('logo_azienda', logo_form.errors)

        files = self.build_valid_files()
        files['protocollo_sanitario'] = SimpleUploadedFile(
            'protocollo.pdf',
            b'a' * (COMPANY_DOCUMENT_MAX_UPLOAD_SIZE + 1),
            content_type='application/pdf',
        )

        document_form = CreaAziendaForm(data=data, files=files)

        self.assertFalse(document_form.is_valid())
        self.assertIn('protocollo_sanitario', document_form.errors)

    def test_admin_create_view_saves_new_profile_fields(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('admin_crea_azienda'),
            data={**self.build_valid_data(), **self.build_valid_files()},
        )

        self.assertRedirects(response, reverse('admin_dashboard'))

        azienda = Azienda.objects.get(ragione_sociale='Azienda Test SRL')

        self.assertEqual(azienda.codice_univoco, 'AB12CD7')
        self.assertEqual(azienda.pec, 'azienda@pec.example.com')
        self.assertEqual(azienda.referente_azienda, 'Mario Rossi')
        self.assertEqual(
            azienda.condizioni_pagamento_riservate,
            'Pagamento completo entro 30 giorni data fattura.',
        )
        self.assertTrue(azienda.logo_azienda.name.endswith('logo.svg'))
        self.assertTrue(azienda.protocollo_sanitario.name.endswith('protocollo.pdf'))
        self.assertEqual(azienda.user.email, 'azienda@example.com')
        self.assertEqual(azienda.user.role, CustomUser.AZIENDA)

    def test_azienda_admin_form_can_reset_linked_account_password(self):
        azienda = self.create_existing_company()

        form = AziendaAdminForm(
            data={
                'ragione_sociale': azienda.ragione_sociale,
                'codice_univoco': azienda.codice_univoco,
                'pec': azienda.pec,
                'referente_azienda': azienda.referente_azienda,
                'codice_fiscale': azienda.codice_fiscale,
                'partita_iva': azienda.partita_iva,
                'email_contatto': azienda.email_contatto,
                'telefono': azienda.telefono,
                'condizioni_pagamento_riservate': azienda.condizioni_pagamento_riservate,
                'contratto_saldato': 'on',
                'user': str(azienda.user.pk),
                'account_email': azienda.user.email,
                'account_password': 'NuovaPassAzienda-456',
                'varie_note': azienda.varie_note,
            },
            instance=azienda,
        )

        self.assertEqual(form.fields['account_password'].widget.input_type, 'text')
        self.assertTrue(form.is_valid(), form.errors)

        form.save()
        azienda.user.refresh_from_db()

        self.assertTrue(azienda.user.check_password('NuovaPassAzienda-456'))


class LavoratoreAdminFormTests(TestCase):
    def setUp(self):
        self.azienda_user = CustomUser.objects.create_user(
            email='azienda-dashboard@example.com',
            password='azienda-pass-123',
            role=CustomUser.AZIENDA,
        )
        self.azienda = Azienda.objects.create(
            user=self.azienda_user,
            ragione_sociale='Azienda Dashboard SRL',
            codice_univoco='AZDASH1',
            pec='dashboard@pec.example.com',
            referente_azienda='Laura Verdi',
            codice_fiscale='VRDLRA80A01H501Z',
            partita_iva='12345098765',
            email_contatto='dashboard@example.com',
            telefono='0212345678',
            condizioni_pagamento_riservate='Pagamento entro 30 giorni.',
        )

    def test_lavoratore_admin_form_can_create_linked_account(self):
        lavoratore = Lavoratore.objects.create(
            azienda=self.azienda,
            nome='Marco',
            cognome='Rossi',
            data_nascita=date(1990, 1, 1),
            codice_fiscale='RSSMRC90A01H501Y',
            mansione='Magazziniere',
            note='',
            attivo=True,
        )

        form = LavoratoreAdminForm(
            data={
                'azienda': str(self.azienda.pk),
                'sede': '',
                'nome': lavoratore.nome,
                'cognome': lavoratore.cognome,
                'data_nascita': lavoratore.data_nascita.isoformat(),
                'codice_fiscale': lavoratore.codice_fiscale,
                'mansione': lavoratore.mansione,
                'note': lavoratore.note,
                'attivo': 'on',
                'user': '',
                'account_email': 'marco.rossi@example.com',
                'account_password': 'OperatorePass-789',
            },
            instance=lavoratore,
        )

        self.assertEqual(form.fields['account_password'].widget.input_type, 'text')
        self.assertTrue(form.is_valid(), form.errors)

        saved_lavoratore = form.save()

        self.assertIsNotNone(saved_lavoratore.user)
        self.assertEqual(saved_lavoratore.user.email, 'marco.rossi@example.com')
        self.assertTrue(saved_lavoratore.user.check_password('OperatorePass-789'))


class AziendaDashboardContactTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email='azienda-contatti@example.com',
            password='azienda-pass-123',
            role=CustomUser.AZIENDA,
        )
        self.azienda = Azienda.objects.create(
            user=self.user,
            ragione_sociale='Azienda Contatti SRL',
            codice_univoco='CONTAT1',
            pec='contatti@pec.example.com',
            referente_azienda='Paolo Neri',
            codice_fiscale='NRIPLA80A01H501Z',
            partita_iva='12345670001',
            email_contatto='contatti@example.com',
            telefono='0612345678',
            condizioni_pagamento_riservate='Pagamento entro 30 giorni.',
        )

    def test_dashboard_shows_centro_delta_contact_box(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('azienda_dashboard'))

        self.assertContains(response, 'Rosanna Cocozza')
        self.assertContains(response, 'rosanna.cocozza@tecnobios.com')
        self.assertContains(response, '351 6572647')
