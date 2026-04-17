from django.db.models.signals import post_delete
from django.dispatch import receiver

from apps.accounts.models import CustomUser

from .models import Azienda, AziendaReadOnlyAccess, Lavoratore


@receiver(post_delete, sender=Azienda)
def delete_linked_company_account(sender, instance, **kwargs):
    if not instance.user_id:
        return
    CustomUser.objects.filter(
        pk=instance.user_id,
        role=CustomUser.AZIENDA,
    ).delete()


@receiver(post_delete, sender=AziendaReadOnlyAccess)
def delete_linked_company_read_only_account(sender, instance, **kwargs):
    if not instance.user_id:
        return
    CustomUser.objects.filter(
        pk=instance.user_id,
        role=CustomUser.AZIENDA,
    ).delete()


@receiver(post_delete, sender=Lavoratore)
def delete_linked_operator_account(sender, instance, **kwargs):
    if not instance.user_id:
        return
    CustomUser.objects.filter(
        pk=instance.user_id,
        role=CustomUser.OPERATORE,
    ).delete()
