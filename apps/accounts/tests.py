from django.test import TestCase
from django.urls import reverse

from .admin import CustomUserChangeForm, CustomUserCreationForm
from .models import CustomUser


class CustomUserAdminFormTests(TestCase):
    def test_creation_form_uses_visible_password_fields_and_hashes_value(self):
        form = CustomUserCreationForm(
            data={
                'email': 'nuovo@example.com',
                'role': CustomUser.AZIENDA,
                'is_active': 'on',
                'password1': 'Pass-chiara-123',
                'password2': 'Pass-chiara-123',
            }
        )

        self.assertEqual(form.fields['password1'].widget.input_type, 'text')
        self.assertEqual(form.fields['password2'].widget.input_type, 'text')
        self.assertTrue(form.is_valid(), form.errors)

        user = form.save()

        self.assertTrue(user.check_password('Pass-chiara-123'))
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
                'password1': 'AdminLimitato-123',
                'password2': 'AdminLimitato-123',
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

        self.assertEqual(form.initial['password'], 'Password gia impostata')
        self.assertEqual(form.fields['new_password'].widget.input_type, 'text')
        self.assertEqual(form.fields['is_active'].label, 'Attivo')
        self.assertTrue(form.is_valid(), form.errors)

        saved_user = form.save()

        self.assertTrue(saved_user.check_password('Nuova-pass-456'))
        self.assertEqual(saved_user.admin_permissions, [CustomUser.ADMIN_PERMISSION_MEDICAL_RECORDS])


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
