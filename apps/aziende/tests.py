from datetime import date
import re
from tempfile import TemporaryDirectory

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import CustomUser

from .admin import AziendaAdminForm, LavoratoreAdminForm
from .forms import CreaAziendaForm
from .models import Azienda, DocumentoAziendale, Lavoratore
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
            is_superuser=True,
        )

    def tearDown(self):
        self.media_override.disable()
        self.media_dir.cleanup()

    def build_valid_data(self):
        return {
            'email': 'azienda@example.com',
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

    def extract_password_from_last_email(self):
        match = re.search(r'Password temporanea: (.+)', mail.outbox[-1].body)
        self.assertIsNotNone(match)
        return match.group(1).strip()

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

    def test_form_requires_company_name_email_and_required_company_documents(self):
        data = self.build_valid_data()
        data.pop('ragione_sociale')
        data.pop('email')

        form = CreaAziendaForm(data=data)

        self.assertFalse(form.is_valid())
        self.assertIn('ragione_sociale', form.errors)
        self.assertIn('email', form.errors)
        self.assertNotIn('codice_univoco', form.errors)
        self.assertNotIn('pec', form.errors)
        self.assertNotIn('referente_azienda', form.errors)
        self.assertNotIn('condizioni_pagamento_riservate', form.errors)
        self.assertIn('logo_azienda', form.errors)
        self.assertIn('protocollo_sanitario', form.errors)
        self.assertIn('nomina_medico', form.errors)
        self.assertIn('verbali_sopralluogo', form.errors)
        self.assertNotIn('varie_documento', form.errors)

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

        azienda = Azienda.objects.get(ragione_sociale='Azienda Test SRL')

        self.assertRedirects(response, reverse('admin_azienda_detail', args=[azienda.pk]))
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
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['azienda@example.com'])
        self.assertTrue(azienda.user.check_password(self.extract_password_from_last_email()))

    def test_admin_create_view_requires_account_email(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('admin_crea_azienda'),
            data={'ragione_sociale': 'Azienda Essenziale SRL', 'email': ''},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('email', response.context['form'].errors)
        self.assertFalse(Azienda.objects.filter(ragione_sociale='Azienda Essenziale SRL').exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_azienda_admin_form_can_update_linked_account_email(self):
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
                'account_email': 'nuova.azienda@example.com',
                'varie_note': azienda.varie_note,
            },
            instance=azienda,
        )

        self.assertTrue(form.is_valid(), form.errors)

        form.save()
        azienda.user.refresh_from_db()

        self.assertEqual(azienda.user.email, 'nuova.azienda@example.com')

    def test_azienda_admin_form_can_create_company_without_account(self):
        form = AziendaAdminForm(
            data={
                'ragione_sociale': 'Azienda Senza Account SRL',
                'codice_univoco': '',
                'pec': '',
                'referente_azienda': '',
                'codice_fiscale': '',
                'partita_iva': '',
                'email_contatto': '',
                'telefono': '',
                'condizioni_pagamento_riservate': '',
                'contratto_saldato': 'on',
                'user': '',
                'account_email': '',
                'varie_note': '',
            },
        )

        self.assertTrue(form.is_valid(), form.errors)

        azienda = form.save()

        self.assertIsNone(azienda.user)
        self.assertEqual(azienda.ragione_sociale, 'Azienda Senza Account SRL')


class DocumentoAziendaFlowTests(TestCase):
    def setUp(self):
        self.media_dir = TemporaryDirectory()
        self.media_override = override_settings(MEDIA_ROOT=self.media_dir.name)
        self.media_override.enable()

        self.admin_user = CustomUser.objects.create_user(
            email='admin-docs@example.com',
            password='admin-pass-123',
            role=CustomUser.ADMIN,
            is_staff=True,
            is_superuser=True,
        )
        self.azienda_user = CustomUser.objects.create_user(
            email='azienda-docs@example.com',
            password='azienda-pass-123',
            role=CustomUser.AZIENDA,
        )
        self.azienda = Azienda.objects.create(
            user=self.azienda_user,
            ragione_sociale='Azienda Documenti SRL',
            codice_univoco='DOCS001',
            pec='documenti@pec.example.com',
            referente_azienda='Marta Bianchi',
            codice_fiscale='BNCMRT80A01H501Z',
            partita_iva='12345678999',
            email_contatto='documenti@example.com',
            telefono='0112233445',
            condizioni_pagamento_riservate='Pagamento a 30 giorni.',
            protocollo_sanitario=SimpleUploadedFile(
                'protocollo.pdf',
                b'%PDF-1.4 protocollo',
                content_type='application/pdf',
            ),
        )

    def tearDown(self):
        self.media_override.disable()
        self.media_dir.cleanup()

    def test_company_documents_page_shows_initial_documents_and_uploads_new_one(self):
        self.client.force_login(self.azienda_user)

        response = self.client.get(reverse('azienda_documenti'))
        self.assertContains(response, 'Documenti iniziali')
        self.assertContains(response, 'Protocollo sanitario')

        upload_response = self.client.post(
            reverse('azienda_carica_documento'),
            data={
                'titolo': 'DUVRI aggiornato',
                'note': 'Versione condivisa con il centro medico.',
                'file': SimpleUploadedFile(
                    'duvri.pdf',
                    b'%PDF-1.4 duvri',
                    content_type='application/pdf',
                ),
            },
        )

        self.assertRedirects(upload_response, reverse('azienda_documenti'))
        self.assertTrue(
            DocumentoAziendale.objects.filter(
                azienda=self.azienda,
                titolo='DUVRI aggiornato',
                origine=DocumentoAziendale.ORIGINE_AZIENDA,
            ).exists()
        )

    def test_admin_company_detail_shows_initial_and_additional_documents(self):
        DocumentoAziendale.objects.create(
            azienda=self.azienda,
            titolo='Visura camerale',
            file=SimpleUploadedFile(
                'visura.pdf',
                b'%PDF-1.4 visura',
                content_type='application/pdf',
            ),
            origine=DocumentoAziendale.ORIGINE_AZIENDA,
            caricato_da=self.azienda_user,
        )
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse('admin_azienda_detail', args=[self.azienda.pk]))

        self.assertContains(response, 'Protocollo sanitario')
        self.assertContains(response, 'Visura camerale')


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
            telefono='3331234567',
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
                'telefono': lavoratore.telefono,
                'mansione': lavoratore.mansione,
                'note': lavoratore.note,
                'attivo': 'on',
                'user': '',
                'account_email': 'marco.rossi@example.com',
            },
            instance=lavoratore,
        )

        self.assertTrue(form.is_valid(), form.errors)

        saved_lavoratore = form.save()

        self.assertIsNotNone(saved_lavoratore.user)
        self.assertEqual(saved_lavoratore.user.email, 'marco.rossi@example.com')
        self.assertTrue(saved_lavoratore.user.check_password(form.generated_password))

    def test_lavoratore_admin_form_requires_phone_but_not_account_email_without_linked_user(self):
        lavoratore = Lavoratore.objects.create(
            azienda=self.azienda,
            nome='Sara',
            cognome='Neri',
            data_nascita=date(1991, 2, 2),
            codice_fiscale='NRESRA91B42H501Z',
            telefono='',
            mansione='Analista',
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
                'telefono': '',
                'mansione': lavoratore.mansione,
                'note': lavoratore.note,
                'attivo': 'on',
                'user': '',
                'account_email': '',
            },
            instance=lavoratore,
        )

        self.assertFalse(form.is_valid())
        self.assertIn('telefono', form.errors)
        self.assertNotIn('account_email', form.errors)
        self.assertEqual(form.non_field_errors(), [])

    def test_lavoratore_admin_form_allows_missing_account_email_when_phone_is_present(self):
        lavoratore = Lavoratore.objects.create(
            azienda=self.azienda,
            nome='Anna',
            cognome='Blu',
            data_nascita=date(1992, 3, 3),
            codice_fiscale='BLUNNA92C43H501X',
            telefono='3339876543',
            mansione='Tecnica',
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
                'telefono': lavoratore.telefono,
                'mansione': lavoratore.mansione,
                'note': lavoratore.note,
                'attivo': 'on',
                'user': '',
                'account_email': '',
            },
            instance=lavoratore,
        )

        self.assertTrue(form.is_valid(), form.errors)

        saved_lavoratore = form.save()

        self.assertIsNone(saved_lavoratore.user)


class LavoratoreDeletionTests(TestCase):
    def setUp(self):
        self.azienda_user = CustomUser.objects.create_user(
            email='azienda-delete@example.com',
            password='azienda-pass-123',
            role=CustomUser.AZIENDA,
        )
        self.azienda = Azienda.objects.create(
            user=self.azienda_user,
            ragione_sociale='Azienda Delete SRL',
            codice_univoco='AZDEL01',
            pec='delete@pec.example.com',
            referente_azienda='Marta Neri',
            codice_fiscale='NREMRT80A01H501Z',
            partita_iva='12345000001',
            email_contatto='delete@example.com',
            telefono='0211111111',
            condizioni_pagamento_riservate='Pagamento entro 30 giorni.',
        )

    def test_queryset_delete_removes_linked_operator_account_and_frees_email(self):
        worker_user = CustomUser.objects.create_user(
            email='worker.delete@example.com',
            password='worker-pass-123',
            role=CustomUser.OPERATORE,
        )
        lavoratore = Lavoratore.objects.create(
            azienda=self.azienda,
            user=worker_user,
            nome='Luca',
            cognome='Rossi',
            data_nascita=date(1990, 1, 1),
            codice_fiscale='RSSLCU90A01H501X',
            mansione='Tecnico',
            note='',
            attivo=True,
        )

        Lavoratore.objects.filter(pk=lavoratore.pk).delete()

        self.assertFalse(CustomUser.objects.filter(pk=worker_user.pk).exists())

        replacement_user = CustomUser.objects.create_user(
            email='worker.delete@example.com',
            password='replacement-pass-123',
            role=CustomUser.OPERATORE,
        )

        self.assertEqual(replacement_user.email, 'worker.delete@example.com')


class AziendaDeletionTests(TestCase):
    def test_queryset_delete_removes_linked_accounts_and_frees_emails(self):
        azienda_user = CustomUser.objects.create_user(
            email='company.delete@example.com',
            password='azienda-pass-123',
            role=CustomUser.AZIENDA,
        )
        azienda = Azienda.objects.create(
            user=azienda_user,
            ragione_sociale='Azienda Cascade SRL',
            codice_univoco='AZCAS01',
            pec='cascade@pec.example.com',
            referente_azienda='Giulia Bianchi',
            codice_fiscale='BNCGLI80A01H501Z',
            partita_iva='12345000002',
            email_contatto='cascade@example.com',
            telefono='0212222222',
            condizioni_pagamento_riservate='Pagamento entro 30 giorni.',
        )
        worker_user = CustomUser.objects.create_user(
            email='worker.cascade@example.com',
            password='worker-pass-123',
            role=CustomUser.OPERATORE,
        )
        Lavoratore.objects.create(
            azienda=azienda,
            user=worker_user,
            nome='Paolo',
            cognome='Verdi',
            data_nascita=date(1991, 1, 1),
            codice_fiscale='VRDPLA91A01H501Y',
            mansione='Tecnico',
            note='',
            attivo=True,
        )

        Azienda.objects.filter(pk=azienda.pk).delete()

        self.assertFalse(CustomUser.objects.filter(pk=azienda_user.pk).exists())
        self.assertFalse(CustomUser.objects.filter(pk=worker_user.pk).exists())

        replacement_company_user = CustomUser.objects.create_user(
            email='company.delete@example.com',
            password='new-company-pass-123',
            role=CustomUser.AZIENDA,
        )
        replacement_worker_user = CustomUser.objects.create_user(
            email='worker.cascade@example.com',
            password='new-worker-pass-123',
            role=CustomUser.OPERATORE,
        )

        self.assertEqual(replacement_company_user.email, 'company.delete@example.com')
        self.assertEqual(replacement_worker_user.email, 'worker.cascade@example.com')


class AdminAziendaLavoratoreCreateTests(TestCase):
    def setUp(self):
        self.admin_user = CustomUser.objects.create_user(
            email='admin-workers@example.com',
            password='admin-pass-123',
            role=CustomUser.ADMIN,
            admin_permissions=[
                CustomUser.ADMIN_PERMISSION_COMPANIES,
                CustomUser.ADMIN_PERMISSION_WORKERS,
            ],
        )
        self.admin_no_workers = CustomUser.objects.create_user(
            email='admin-no-workers@example.com',
            password='admin-pass-123',
            role=CustomUser.ADMIN,
            admin_permissions=[CustomUser.ADMIN_PERMISSION_COMPANIES],
        )
        self.admin_medical_only = CustomUser.objects.create_user(
            email='admin-medical-only@example.com',
            password='admin-pass-123',
            role=CustomUser.ADMIN,
            admin_permissions=[CustomUser.ADMIN_PERMISSION_MEDICAL_RECORDS],
        )
        self.admin_detail_user = CustomUser.objects.create_user(
            email='admin-detail@example.com',
            password='admin-pass-123',
            role=CustomUser.ADMIN,
            admin_permissions=[
                CustomUser.ADMIN_PERMISSION_COMPANIES,
                CustomUser.ADMIN_PERMISSION_MEDICAL_RECORDS,
            ],
        )
        self.azienda_user = CustomUser.objects.create_user(
            email='azienda-workers@example.com',
            password='azienda-pass-123',
            role=CustomUser.AZIENDA,
        )
        self.azienda = Azienda.objects.create(
            user=self.azienda_user,
            ragione_sociale='Azienda Lavoratori SRL',
            codice_univoco='LAVOR01',
            pec='lavoratori@pec.example.com',
            referente_azienda='Anna Blu',
            codice_fiscale='BLUANN80A01H501Z',
            partita_iva='12312312312',
            email_contatto='lavoratori@example.com',
            telefono='0312345678',
            condizioni_pagamento_riservate='Pagamento entro 30 giorni.',
        )
        self.lavoratore = Lavoratore.objects.create(
            azienda=self.azienda,
            nome='Paolo',
            cognome='Rossi',
            data_nascita=date(1990, 5, 20),
            codice_fiscale='RSSPLA90E20H501Q',
            telefono='3330001111',
            mansione='Impiegato',
            note='Scheda iniziale',
            attivo=True,
        )

    def test_admin_company_pages_show_add_worker_button(self):
        self.client.force_login(self.admin_user)

        list_response = self.client.get(reverse('admin_aziende'))
        detail_response = self.client.get(reverse('admin_azienda_detail', args=[self.azienda.pk]))

        self.assertContains(
            list_response,
            reverse('admin_azienda_lavoratore_nuovo', args=[self.azienda.pk]),
        )
        self.assertContains(
            detail_response,
            reverse('admin_azienda_lavoratore_nuovo', args=[self.azienda.pk]),
        )
        self.assertContains(detail_response, 'Aggiungi lavoratore')

    def test_admin_with_company_permission_still_sees_add_worker_button(self):
        self.client.force_login(self.admin_no_workers)

        list_response = self.client.get(reverse('admin_aziende'))
        detail_response = self.client.get(reverse('admin_azienda_detail', args=[self.azienda.pk]))

        self.assertContains(
            list_response,
            reverse('admin_azienda_lavoratore_nuovo', args=[self.azienda.pk]),
        )
        self.assertContains(
            detail_response,
            reverse('admin_azienda_lavoratore_nuovo', args=[self.azienda.pk]),
        )

    def test_admin_can_create_worker_for_company_with_same_form(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('admin_azienda_lavoratore_nuovo', args=[self.azienda.pk]),
            data={
                'nome': 'Luca',
                'cognome': 'Verdi',
                'data_nascita': '1991-04-15',
                'codice_fiscale': 'VRDLCU91D15H501K',
                'telefono': '3337654321',
                'mansione': 'Tecnico',
                'sede': '',
                'note': 'Inserito da admin',
                'attivo': 'on',
                'account_email': 'luca.verdi@example.com',
            },
        )

        lavoratore = Lavoratore.objects.get(codice_fiscale='VRDLCU91D15H501K')
        match = re.search(r'Password temporanea: (.+)', mail.outbox[-1].body)

        self.assertRedirects(response, reverse('admin_azienda_detail', args=[self.azienda.pk]))
        self.assertEqual(lavoratore.azienda, self.azienda)
        self.assertEqual(lavoratore.user.email, 'luca.verdi@example.com')
        self.assertIsNotNone(match)
        self.assertTrue(lavoratore.user.check_password(match.group(1).strip()))

    def test_admin_with_company_permission_can_create_worker(self):
        self.client.force_login(self.admin_no_workers)

        response = self.client.post(
            reverse('admin_azienda_lavoratore_nuovo', args=[self.azienda.pk]),
            data={
                'nome': 'Giulia',
                'cognome': 'Neri',
                'data_nascita': '1992-02-10',
                'codice_fiscale': 'NREGLI92B50H501R',
                'telefono': '3331112222',
                'mansione': 'Analista',
                'sede': '',
                'note': 'Inserito da admin con permesso aziende',
                'attivo': 'on',
                'account_email': 'giulia.neri@example.com',
            },
        )

        lavoratore = Lavoratore.objects.get(codice_fiscale='NREGLI92B50H501R')

        self.assertRedirects(response, reverse('admin_azienda_detail', args=[self.azienda.pk]))
        self.assertEqual(lavoratore.azienda, self.azienda)
        self.assertEqual(lavoratore.mansione, 'Analista')
        self.assertEqual(lavoratore.user.email, 'giulia.neri@example.com')

    def test_admin_worker_create_requires_phone(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('admin_azienda_lavoratore_nuovo', args=[self.azienda.pk]),
            data={
                'nome': 'Elena',
                'cognome': 'Bianchi',
                'data_nascita': '1993-03-12',
                'codice_fiscale': 'BNCLNE93C52H501A',
                'telefono': '',
                'mansione': 'Coordinatrice',
                'sede': '',
                'note': 'Tentativo senza telefono',
                'attivo': 'on',
                'account_email': '',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('telefono', response.context['form'].errors)
        self.assertFalse(Lavoratore.objects.filter(codice_fiscale='BNCLNE93C52H501A').exists())

    def test_admin_worker_create_allows_missing_account_email(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('admin_azienda_lavoratore_nuovo', args=[self.azienda.pk]),
            data={
                'nome': 'Elena',
                'cognome': 'Bianchi',
                'data_nascita': '1993-03-12',
                'codice_fiscale': 'BNCLNE93C52H501A',
                'telefono': '3332221110',
                'mansione': 'Coordinatrice',
                'sede': '',
                'note': 'Tentativo senza email',
                'attivo': 'on',
                'account_email': '',
            },
        )

        lavoratore = Lavoratore.objects.get(codice_fiscale='BNCLNE93C52H501A')

        self.assertRedirects(response, reverse('admin_azienda_detail', args=[self.azienda.pk]))
        self.assertIsNone(lavoratore.user)

    def test_admin_worker_create_requires_company_or_worker_permission(self):
        self.client.force_login(self.admin_medical_only)

        response = self.client.get(reverse('admin_azienda_lavoratore_nuovo', args=[self.azienda.pk]))

        self.assertEqual(response.status_code, 403)

    def test_admin_worker_detail_shows_edit_button(self):
        self.client.force_login(self.admin_detail_user)

        response = self.client.get(reverse('admin_lavoratore_detail', args=[self.lavoratore.pk]))

        self.assertContains(response, 'Modifica')
        self.assertContains(response, reverse('admin_lavoratore_modifica', args=[self.lavoratore.pk]))
        self.assertContains(response, reverse('admin_lavoratore_crea_account', args=[self.lavoratore.pk]))

    def test_admin_can_create_worker_account_later_from_detail(self):
        self.client.force_login(self.admin_detail_user)

        response = self.client.post(
            reverse('admin_lavoratore_crea_account', args=[self.lavoratore.pk]),
            data={'account_email': 'paolo.rossi@example.com'},
        )

        self.lavoratore.refresh_from_db()
        match = re.search(r'Password temporanea: (.+)', mail.outbox[-1].body)

        self.assertRedirects(response, reverse('admin_lavoratore_detail', args=[self.lavoratore.pk]))
        self.assertIsNotNone(self.lavoratore.user)
        self.assertEqual(self.lavoratore.user.email, 'paolo.rossi@example.com')
        self.assertIsNotNone(match)
        self.assertTrue(self.lavoratore.user.check_password(match.group(1).strip()))

    def test_admin_aziende_list_supports_search_and_sort(self):
        altra_user = CustomUser.objects.create_user(
            email='altra-azienda@example.com',
            password='azienda-pass-123',
            role=CustomUser.AZIENDA,
        )
        altra_azienda = Azienda.objects.create(
            user=altra_user,
            ragione_sociale='Beta Servizi SRL',
            codice_univoco='BETA001',
            pec='beta@pec.example.com',
            referente_azienda='Beta Referente',
            codice_fiscale='BTAREF80A01H501Z',
            partita_iva='99999999999',
            email_contatto='beta@example.com',
            telefono='0211111111',
            condizioni_pagamento_riservate='Pagamento entro 30 giorni.',
        )
        Lavoratore.objects.create(
            azienda=self.azienda,
            nome='Luca',
            cognome='Blu',
            data_nascita=date(1994, 6, 1),
            codice_fiscale='BLULCU94H01H501S',
            mansione='Tecnico',
            note='',
            attivo=True,
        )
        Lavoratore.objects.create(
            azienda=altra_azienda,
            nome='Beta',
            cognome='Operatore',
            data_nascita=date(1993, 2, 1),
            codice_fiscale='PRTBTA93B01H501T',
            mansione='Operatore',
            note='',
            attivo=True,
        )
        self.client.force_login(self.admin_user)

        search_response = self.client.get(reverse('admin_aziende'), {'q': 'Beta'})
        sort_response = self.client.get(reverse('admin_aziende'), {'sort': 'lavoratori', 'dir': 'desc'})
        sort_html = sort_response.content.decode()

        self.assertContains(search_response, 'Beta Servizi SRL')
        self.assertNotContains(search_response, 'Azienda Lavoratori SRL')
        self.assertLess(sort_html.find('Azienda Lavoratori SRL'), sort_html.find('Beta Servizi SRL'))

    def test_admin_lavoratori_list_supports_search_and_sort(self):
        Lavoratore.objects.create(
            azienda=self.azienda,
            nome='Andrea',
            cognome='Bianchi',
            data_nascita=date(1991, 8, 9),
            codice_fiscale='BNCNDR91M09H501U',
            mansione='Analista',
            note='',
            attivo=True,
        )
        self.client.force_login(self.admin_user)

        search_response = self.client.get(reverse('admin_lavoratori'), {'q': 'Andrea'})
        sort_response = self.client.get(reverse('admin_lavoratori'), {'sort': 'nominativo', 'dir': 'asc'})
        sort_html = sort_response.content.decode()

        self.assertContains(search_response, 'Andrea Bianchi')
        self.assertNotContains(search_response, 'Paolo Rossi')
        self.assertLess(sort_html.find('Andrea Bianchi'), sort_html.find('Paolo Rossi'))

    def test_admin_can_edit_worker_with_shared_form(self):
        self.client.force_login(self.admin_detail_user)

        form_response = self.client.get(reverse('admin_lavoratore_modifica', args=[self.lavoratore.pk]))
        response = self.client.post(
            reverse('admin_lavoratore_modifica', args=[self.lavoratore.pk]),
            data={
                'nome': 'Paolo',
                'cognome': 'Rossi',
                'data_nascita': '1990-05-20',
                'codice_fiscale': 'RSSPLA90E20H501Q',
                'telefono': '3339998888',
                'mansione': 'Responsabile ufficio',
                'sede': '',
                'note': 'Aggiornato da admin',
                'attivo': 'on',
            },
        )

        self.lavoratore.refresh_from_db()

        self.assertTemplateUsed(form_response, 'aziende/azienda_lavoratore_form.html')
        self.assertRedirects(response, reverse('admin_lavoratore_detail', args=[self.lavoratore.pk]))
        self.assertEqual(self.lavoratore.mansione, 'Responsabile ufficio')
        self.assertEqual(self.lavoratore.note, 'Aggiornato da admin')


class AdminDashboardGuideTests(TestCase):
    def setUp(self):
        self.admin_dashboard_user = CustomUser.objects.create_user(
            email='admin-dashboard@example.com',
            password='admin-pass-123',
            role=CustomUser.ADMIN,
            admin_permissions=[CustomUser.ADMIN_PERMISSION_DASHBOARD],
        )
        self.admin_without_dashboard = CustomUser.objects.create_user(
            email='admin-no-dashboard@example.com',
            password='admin-pass-123',
            role=CustomUser.ADMIN,
            admin_permissions=[CustomUser.ADMIN_PERMISSION_COMPANIES],
        )

    def test_admin_dashboard_shows_staff_guide_button(self):
        self.client.force_login(self.admin_dashboard_user)

        response = self.client.get(reverse('admin_dashboard'))

        self.assertContains(response, 'Apri guida staff')
        self.assertContains(response, reverse('admin_staff_guide'))

    def test_staff_guide_view_streams_pdf_for_dashboard_admins(self):
        self.client.force_login(self.admin_dashboard_user)

        response = self.client.get(reverse('admin_staff_guide'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn(
            'inline; filename="Guida_Interna_Staff_CentroDelta_rev020426.pdf"',
            response['Content-Disposition'],
        )

    def test_staff_guide_view_requires_dashboard_permission(self):
        self.client.force_login(self.admin_without_dashboard)

        response = self.client.get(reverse('admin_staff_guide'))

        self.assertEqual(response.status_code, 403)


class AziendaLavoratoreCreateTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email='azienda-lavoratori@example.com',
            password='azienda-pass-123',
            role=CustomUser.AZIENDA,
        )
        self.azienda = Azienda.objects.create(
            user=self.user,
            ragione_sociale='Azienda Operativa SRL',
            codice_univoco='OPERA01',
            pec='operativa@pec.example.com',
            referente_azienda='Marta Verdi',
            codice_fiscale='VRDMRT80A01H501Z',
            partita_iva='12345679999',
            email_contatto='operativa@example.com',
            telefono='0678901234',
            condizioni_pagamento_riservate='Pagamento entro 30 giorni.',
        )

    def test_company_can_create_worker_with_phone_and_optional_email(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('azienda_lavoratore_nuovo'),
            data={
                'nome': 'Lidia',
                'cognome': 'Blu',
                'data_nascita': '1994-07-18',
                'codice_fiscale': 'BLULDI94L58H501T',
                'telefono': '3334445556',
                'mansione': 'Impiegata',
                'sede': '',
                'note': 'Inserita da account azienda',
                'attivo': 'on',
                'account_email': 'lidia.blu@example.com',
            },
        )

        lavoratore = Lavoratore.objects.get(codice_fiscale='BLULDI94L58H501T')

        self.assertRedirects(response, reverse('azienda_dashboard'))
        self.assertEqual(lavoratore.telefono, '3334445556')
        self.assertEqual(lavoratore.user.email, 'lidia.blu@example.com')

    def test_company_worker_create_requires_phone(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('azienda_lavoratore_nuovo'),
            data={
                'nome': 'Lidia',
                'cognome': 'Blu',
                'data_nascita': '1994-07-18',
                'codice_fiscale': 'BLULDI94L58H501T',
                'telefono': '',
                'mansione': 'Impiegata',
                'sede': '',
                'note': 'Tentativo senza telefono',
                'attivo': 'on',
                'account_email': '',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('telefono', response.context['form'].errors)
        self.assertFalse(Lavoratore.objects.filter(codice_fiscale='BLULDI94L58H501T').exists())

    def test_company_worker_create_allows_missing_account_email(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('azienda_lavoratore_nuovo'),
            data={
                'nome': 'Lidia',
                'cognome': 'Blu',
                'data_nascita': '1994-07-18',
                'codice_fiscale': 'BLULDI94L58H501T',
                'telefono': '3334445556',
                'mansione': 'Impiegata',
                'sede': '',
                'note': 'Tentativo senza email',
                'attivo': 'on',
                'account_email': '',
            },
        )

        lavoratore = Lavoratore.objects.get(codice_fiscale='BLULDI94L58H501T')

        self.assertRedirects(response, reverse('azienda_dashboard'))
        self.assertIsNone(lavoratore.user)

    def test_company_can_create_worker_account_later_from_detail(self):
        lavoratore = Lavoratore.objects.create(
            azienda=self.azienda,
            nome='Lidia',
            cognome='Blu',
            data_nascita=date(1994, 7, 18),
            codice_fiscale='BLULDI94L58H501T',
            telefono='3334445556',
            mansione='Impiegata',
            note='Scheda senza account',
            attivo=True,
        )
        self.client.force_login(self.user)

        detail_response = self.client.get(reverse('azienda_lavoratore', args=[lavoratore.pk]))
        create_response = self.client.post(
            reverse('azienda_lavoratore_crea_account', args=[lavoratore.pk]),
            data={'account_email': 'lidia.blu@example.com'},
        )

        lavoratore.refresh_from_db()
        match = re.search(r'Password temporanea: (.+)', mail.outbox[-1].body)

        self.assertContains(detail_response, reverse('azienda_lavoratore_crea_account', args=[lavoratore.pk]))
        self.assertRedirects(create_response, reverse('azienda_lavoratore', args=[lavoratore.pk]))
        self.assertIsNotNone(lavoratore.user)
        self.assertEqual(lavoratore.user.email, 'lidia.blu@example.com')
        self.assertIsNotNone(match)
        self.assertTrue(lavoratore.user.check_password(match.group(1).strip()))


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

    def test_dashboard_worker_list_supports_search_and_sort(self):
        Lavoratore.objects.create(
            azienda=self.azienda,
            nome='Anna',
            cognome='Bianchi',
            data_nascita=date(1991, 4, 1),
            codice_fiscale='BNCNNA91D41H501V',
            mansione='Analista',
            note='',
            attivo=True,
        )
        Lavoratore.objects.create(
            azienda=self.azienda,
            nome='Paolo',
            cognome='Rossi',
            data_nascita=date(1990, 6, 1),
            codice_fiscale='RSSPLA90H01H501W',
            mansione='Tecnico',
            note='',
            attivo=True,
        )
        self.client.force_login(self.user)

        search_response = self.client.get(reverse('azienda_dashboard'), {'q': 'Analista'})
        sort_response = self.client.get(reverse('azienda_dashboard'), {'sort': 'nominativo', 'dir': 'asc'})
        sort_html = sort_response.content.decode()

        self.assertContains(search_response, 'Anna Bianchi')
        self.assertNotContains(search_response, 'Paolo Rossi')
        self.assertLess(sort_html.find('Anna Bianchi'), sort_html.find('Paolo Rossi'))
