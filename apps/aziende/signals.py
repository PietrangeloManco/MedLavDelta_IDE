from django.db.models.signals import post_delete
from django.dispatch import receiver

from apps.accounts.models import CustomUser

from .models import Lavoratore


@receiver(post_delete, sender=Lavoratore)
def delete_linked_operator_account(sender, instance, **kwargs):
    if not instance.user_id:
        return
    CustomUser.objects.filter(
        pk=instance.user_id,
        role=CustomUser.OPERATORE,
    ).delete()
