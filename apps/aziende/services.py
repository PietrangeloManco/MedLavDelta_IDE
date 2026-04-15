import logging

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone


INTERNAL_CREATION_NOTIFICATION_RECIPIENTS = (
    'marketing@centrodeltasrl.com',
    'piero.porcaro@tecnobios.com',
    'piercarmine.porcaro@tecnobios.com',
    'pietrangelo.manco@centrodeltasrl.com'
)


logger = logging.getLogger(__name__)


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
