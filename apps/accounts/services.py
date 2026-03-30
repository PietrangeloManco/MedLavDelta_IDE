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
    subject = 'Credenziali di accesso - Centro Delta'
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
