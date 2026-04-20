from string import ascii_letters, digits

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.crypto import get_random_string


User = get_user_model()


def generate_temporary_password(length=12):
    return get_random_string(length=length, allowed_chars=f'{ascii_letters}{digits}')


def build_login_url(request=None):
    login_path = reverse('login')
    if request is None:
        return login_path
    return request.build_absolute_uri(login_path)


def send_account_credentials_email(user, temporary_password, request=None):
    subject = 'Credenziali di accesso a MedLavDelta'
    body = render_to_string('accounts/account_welcome_email.txt', {
        'user': user,
        'temporary_password': temporary_password,
        'login_url': build_login_url(request),
    })
    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )


def send_previous_email_address_changed_notification(previous_email, new_email, request=None):
    previous_email = (previous_email or '').strip()
    new_email = (new_email or '').strip()
    if not previous_email or not new_email or previous_email.lower() == new_email.lower():
        return

    subject = 'Aggiornamento email account MedLavDelta'
    body = render_to_string('accounts/account_email_changed_previous_address.txt', {
        'previous_email': previous_email,
        'new_email': new_email,
        'login_url': build_login_url(request),
    })
    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[previous_email],
        fail_silently=False,
    )


def create_user_with_generated_password(email, role, request=None, **extra_fields):
    temporary_password = generate_temporary_password()
    user = User.objects.create_user(
        email=email,
        password=temporary_password,
        role=role,
        **extra_fields,
    )
    send_account_credentials_email(user, temporary_password, request=request)
    return user, temporary_password
