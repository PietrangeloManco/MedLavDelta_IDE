from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import CustomUser

from .forms import CreaAziendaForm
from .models import Azienda
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

    def test_form_requires_new_company_profile_fields(self):
        data = self.build_valid_data()
        files = self.build_valid_files()

        data.pop('codice_univoco')
        data.pop('pec')
        data.pop('referente_azienda')
        files.pop('logo_azienda')

        form = CreaAziendaForm(data=data, files=files)

        self.assertFalse(form.is_valid())
        self.assertIn('codice_univoco', form.errors)
        self.assertIn('pec', form.errors)
        self.assertIn('referente_azienda', form.errors)
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
        self.assertTrue(azienda.logo_azienda.name.endswith('logo.svg'))
        self.assertTrue(azienda.protocollo_sanitario.name.endswith('protocollo.pdf'))
        self.assertEqual(azienda.user.email, 'azienda@example.com')
        self.assertEqual(azienda.user.role, CustomUser.AZIENDA)
