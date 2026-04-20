from django.contrib.admin.sites import AdminSite
from django.core import mail
from django.test import RequestFactory, TestCase
from django.urls import reverse

from .admin import CustomUserAdmin, CustomUserChangeForm, CustomUserCreationForm
from .models import CustomUser


class CustomUserAdminFormTests(TestCase):
    def setUp(self):
        self.request_factory = RequestFactory()
        self.admin_site = AdminSite()

    def test_creation_form_generates_password_and_hashes_value(self):
        form = CustomUserCreationForm(
            data={
                'email': 'nuovo@example.com',
                'role': CustomUser.AZIENDA,
                'is_active': 'on',
            }
        )

        self.assertNotIn('password1', form.fields)
        self.assertNotIn('password2', form.fields)
        self.assertTrue(form.is_valid(), form.errors)

        user = form.save()

        self.assertTrue(user.check_password(form.generated_password))
        self.assertEqual(user.admin_permissions, [])

    def test_creation_form_can_create_limited_admin_with_permissions(self):
        form = CustomUserCreationForm(
            data={
                'email': 'admin.limitato@example.com',
                'role': CustomUser.ADMIN,
                'is_active': 'on',
                'admin_permissions': [
                    CustomUser.ADMIN_PERMISSION_COMPANIES,
                    CustomUser.ADMIN_PERMISSION_COMPANY_DOCUMENTS,
                ],
            }
        )

        self.assertTrue(form.is_valid(), form.errors)

        user = form.save()

        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_staff)
        self.assertEqual(
            user.admin_permissions,
            [
                CustomUser.ADMIN_PERMISSION_COMPANIES,
                CustomUser.ADMIN_PERMISSION_COMPANY_DOCUMENTS,
            ],
        )

    def test_change_form_resets_password_and_updates_admin_permissions(self):
        user = CustomUser.objects.create_user(
            email='utente@example.com',
            password='vecchia-pass-123',
            role=CustomUser.ADMIN,
            admin_permissions=[CustomUser.ADMIN_PERMISSION_WORKERS],
        )

        form = CustomUserChangeForm(
            data={
                'email': user.email,
                'role': user.role,
                'password': user.password,
                'new_password': 'Nuova-pass-456',
                'is_active': 'on',
                'admin_permissions': [CustomUser.ADMIN_PERMISSION_MEDICAL_RECORDS],
            },
            instance=user,
        )

        self.assertEqual(form.initial['password'], 'Password già impostata')
        self.assertEqual(form.fields['new_password'].widget.input_type, 'text')
        self.assertEqual(form.fields['is_active'].label, 'Attivo')
        self.assertTrue(form.is_valid(), form.errors)

        saved_user = form.save()

        self.assertTrue(saved_user.check_password('Nuova-pass-456'))
        self.assertEqual(saved_user.admin_permissions, [CustomUser.ADMIN_PERMISSION_MEDICAL_RECORDS])

    def test_super_admin_email_change_notifies_previous_address(self):
        super_admin = CustomUser.objects.create_user(
            email='superadmin@example.com',
            password='super-pass-123',
            role=CustomUser.ADMIN,
            is_staff=True,
            is_superuser=True,
        )
        user = CustomUser.objects.create_user(
            email='vecchia@example.com',
            password='utente-pass-123',
            role=CustomUser.AZIENDA,
        )
        form = CustomUserChangeForm(
            data={
                'email': 'nuova@example.com',
                'role': user.role,
                'password': user.password,
                'new_password': '',
                'is_active': 'on',
            },
            instance=user,
        )

        self.assertTrue(form.is_valid(), form.errors)

        request = self.request_factory.post('/admin/accounts/customuser/change/')
        request.user = super_admin
        model_admin = CustomUserAdmin(CustomUser, self.admin_site)
        mail.outbox.clear()

        saved_user = form.save(commit=False)
        model_admin.save_model(request, saved_user, form, change=True)

        user.refresh_from_db()

        self.assertEqual(user.email, 'nuova@example.com')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['vecchia@example.com'])
        self.assertIn('nuova@example.com', mail.outbox[0].body)


class DashboardRouterTests(TestCase):
    def test_limited_admin_is_redirected_to_first_available_section(self):
        user = CustomUser.objects.create_user(
            email='admin.routing@example.com',
            password='admin-pass-123',
            role=CustomUser.ADMIN,
            admin_permissions=[CustomUser.ADMIN_PERMISSION_COMPANIES],
        )
        self.client.force_login(user)

        response = self.client.get(reverse('dashboard'))

        self.assertRedirects(response, reverse('admin_aziende'))


class PasswordResetFlowTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email='azienda-reset@example.com',
            password='password-iniziale-123',
            role=CustomUser.AZIENDA,
        )

    def test_login_page_shows_password_reset_link(self):
        response = self.client.get(reverse('login'))

        self.assertContains(response, reverse('password_reset'))
        self.assertContains(response, 'Password dimenticata?')

    def test_password_reset_request_sends_email(self):
        response = self.client.post(
            reverse('password_reset'),
            data={'email': self.user.email},
        )

        self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Reimposta la password di MedLavDelta', mail.outbox[0].subject)
        self.assertIn('/accounts/reset/', mail.outbox[0].body)
