from django.test import TestCase

from .admin import CustomUserChangeForm, CustomUserCreationForm
from .models import CustomUser


class CustomUserAdminFormTests(TestCase):
    def test_creation_form_uses_visible_password_fields_and_hashes_value(self):
        form = CustomUserCreationForm(
            data={
                'email': 'nuovo@example.com',
                'role': CustomUser.AZIENDA,
                'password1': 'Pass-chiara-123',
                'password2': 'Pass-chiara-123',
            }
        )

        self.assertEqual(form.fields['password1'].widget.input_type, 'text')
        self.assertEqual(form.fields['password2'].widget.input_type, 'text')
        self.assertTrue(form.is_valid(), form.errors)

        user = form.save()

        self.assertTrue(user.check_password('Pass-chiara-123'))

    def test_change_form_resets_password_from_visible_new_password_field(self):
        user = CustomUser.objects.create_user(
            email='utente@example.com',
            password='vecchia-pass-123',
            role=CustomUser.OPERATORE,
        )

        form = CustomUserChangeForm(
            data={
                'email': user.email,
                'role': user.role,
                'password': user.password,
                'new_password': 'Nuova-pass-456',
                'is_active': 'on',
            },
            instance=user,
        )

        self.assertEqual(form.initial['password'], 'Password gia impostata')
        self.assertEqual(form.fields['new_password'].widget.input_type, 'text')
        self.assertEqual(form.fields['is_active'].label, 'Attivo')
        self.assertTrue(form.is_valid(), form.errors)

        saved_user = form.save()

        self.assertTrue(saved_user.check_password('Nuova-pass-456'))
