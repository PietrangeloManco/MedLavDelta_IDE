import logging

from django.conf import settings
from django.core.mail import EmailMessage, send_mail
from django.utils import timezone


INTERNAL_CREATION_NOTIFICATION_RECIPIENTS = (
    'marketing@centrodeltasrl.com',
    'piero.porcaro@tecnobios.com',
    'piercarmine.porcaro@tecnobios.com',
    'pietrangelo.manco@centrodeltasrl.com'
)


logger = logging.getLogger(__name__)


def _unique_emails(emails):
    unique_emails = []
    seen = set()
    for email in emails or []:
        cleaned_email = (email or '').strip()
        if not cleaned_email:
            continue
        email_key = cleaned_email.lower()
        if email_key in seen:
            continue
        seen.add(email_key)
        unique_emails.append(cleaned_email)
    return unique_emails


def split_email_recipients(to_emails, cc_emails=None):
    to_list = _unique_emails(to_emails)
    to_keys = {email.lower() for email in to_list}
    cc_list = [
        email for email in _unique_emails(cc_emails)
        if email.lower() not in to_keys
    ]
    return to_list, cc_list


def send_platform_email(subject, message, to_emails, *, cc_emails=None):
    to_list, cc_list = split_email_recipients(to_emails, cc_emails)
    if not to_list and not cc_list:
        return

    try:
        email = EmailMessage(
            subject=subject,
            body=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=to_list,
            cc=cc_list,
        )
        email.send(fail_silently=False)
    except Exception:
        logger.exception(
            'Errore invio email. Subject=%s, From=%s, To=%s, Cc=%s',
            subject,
            settings.DEFAULT_FROM_EMAIL,
            ', '.join(to_list),
            ', '.join(cc_list),
        )


def get_company_notification_recipients(azienda, *, extra_to=None):
    to_emails = [azienda.primary_notification_email, *(extra_to or [])]
    return split_email_recipients(to_emails, azienda.notification_cc_list)


def send_company_notification_email(azienda, subject, message, *, extra_to=None):
    to_list, cc_list = get_company_notification_recipients(azienda, extra_to=extra_to)
    send_platform_email(subject, message, to_list, cc_emails=cc_list)


def _format_actor(request=None):
    user = getattr(request, 'user', None)
    if not getattr(user, 'is_authenticated', False):
        return 'Sistema'

    role_label = user.get_role_display() if hasattr(user, 'get_role_display') else getattr(user, 'role', '')
    if role_label:
        return f'{user.email} ({role_label})'
    return user.email


def _format_timestamp(value):
    if not value:
        return '-'
    return timezone.localtime(value).strftime('%d/%m/%Y %H:%M')


def _send_internal_creation_notification(subject, message):
    recipient_list = [email for email in INTERNAL_CREATION_NOTIFICATION_RECIPIENTS if email]
    if not recipient_list:
        return

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_list,
            fail_silently=False,
        )
    except Exception:
        logger.exception(
            'Errore invio email notifica creazione. Subject=%s, From=%s, To=%s',
            subject,
            settings.DEFAULT_FROM_EMAIL,
            ', '.join(recipient_list),
        )


def send_new_company_created_notification(azienda, request=None):
    subject = f'Nuova azienda inserita su MedLavDelta: {azienda.display_name}'
    body = '\n'.join([
        "E' stata inserita una nuova azienda su MedLavDelta.",
        '',
        f'Azienda: {azienda.display_name}',
        f'Email account: {azienda.user.email if azienda.user_id else "-"}',
        f'Email contatto: {azienda.email_contatto or "-"}',
        f'Referente azienda: {azienda.referente_azienda or "-"}',
        f'Partita IVA: {azienda.partita_iva or "-"}',
        f'Codice fiscale: {azienda.codice_fiscale or "-"}',
        f'Inserita da: {_format_actor(request)}',
        f'Data inserimento: {_format_timestamp(azienda.data_registrazione)}',
        '',
        'Email automatica generata dalla piattaforma MedLavDelta.',
    ])
    _send_internal_creation_notification(subject, body)


def send_new_worker_created_notification(lavoratore, request=None):
    subject = f'Nuovo lavoratore inserito su MedLavDelta: {lavoratore.nome_completo}'
    body = '\n'.join([
        "E' stato inserito un nuovo lavoratore su MedLavDelta.",
        '',
        f'Lavoratore: {lavoratore.nome_completo}',
        f'Azienda: {lavoratore.azienda.display_name}',
        f'Sede: {lavoratore.sede or "-"}',
        f'Mansione: {lavoratore.mansione or "-"}',
        f'Codice fiscale: {lavoratore.codice_fiscale or "-"}',
        f'Telefono: {lavoratore.telefono or "-"}',
        f'Email account: {lavoratore.user.email if lavoratore.user_id else "-"}',
        f'Inserito da: {_format_actor(request)}',
        f'Data inserimento: {_format_timestamp(lavoratore.data_inserimento)}',
        '',
        'Email automatica generata dalla piattaforma MedLavDelta.',
    ])
    _send_internal_creation_notification(subject, body)
