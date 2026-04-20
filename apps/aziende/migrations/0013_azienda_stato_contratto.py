from django.db import migrations, models


def copy_contract_status_forward(apps, schema_editor):
    Azienda = apps.get_model('aziende', 'Azienda')
    Azienda.objects.filter(contratto_saldato=True).update(stato_contratto='saldato')
    Azienda.objects.filter(contratto_saldato=False).update(stato_contratto='non_saldato')


def copy_contract_status_backward(apps, schema_editor):
    Azienda = apps.get_model('aziende', 'Azienda')
    Azienda.objects.filter(stato_contratto='saldato').update(contratto_saldato=True)
    Azienda.objects.exclude(stato_contratto='saldato').update(contratto_saldato=False)


class Migration(migrations.Migration):

    dependencies = [
        ('aziende', '0012_azienda_email_notifiche_cc_aziendareadonlyaccess'),
    ]

    operations = [
        migrations.AddField(
            model_name='azienda',
            name='stato_contratto',
            field=models.CharField(
                choices=[
                    ('saldato', 'Saldato'),
                    ('in_attesa_pagamento', 'In attesa di pagamento'),
                    ('non_saldato', 'Non saldato'),
                ],
                default='saldato',
                help_text="Se non saldato, l'azienda vedrà un avviso e le funzionalità saranno limitate.",
                max_length=30,
            ),
        ),
        migrations.RunPython(copy_contract_status_forward, copy_contract_status_backward),
        migrations.RemoveField(
            model_name='azienda',
            name='contratto_saldato',
        ),
    ]
