from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.core.mail import send_mail
from django.conf import settings
import logging
from apps.accounts.mixins import AdminRequiredMixin, AziendaRequiredMixin, OperatoreRequiredMixin
from apps.accounts.models import CustomUser
from .models import Azienda, Lavoratore, Sede
from .forms import CreaAziendaForm, LavoratoreForm
from apps.sanitaria.models import EsitoIdoneita, CartellaClinica, DocumentoSanitario
from apps.sanitaria.forms import DocumentoSanitarioForm, EsitoIdoneitaForm
from datetime import timedelta
from django.utils import timezone

CENTRO_DELTA_CONTACT = {
    'nome': 'Rosanna Cocozza',
    'email': 'rosanna.cocozza@tecnobios.com',
    'telefono': '351 6572647',
    'ruolo': 'Referente Centro Delta',
}


def send_notification_email(subject, message, recipients):
    recipient_list = [email for email in recipients if email]
    if not recipient_list:
        return
    logger = logging.getLogger(__name__)
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
            "Errore invio email. Subject=%s, From=%s, To=%s",
            subject,
            settings.DEFAULT_FROM_EMAIL,
            ", ".join(recipient_list),
        )

# ─── ADMIN ────────────────────────────────────────────────────────────────────

class AdminDashboardView(AdminRequiredMixin, View):
    def get(self, request):
        oggi = timezone.now().date()
        soglia = oggi + timedelta(days=30)
        
        scadenze_imminenti = EsitoIdoneita.objects.filter(
            data_scadenza__gte=oggi,
            data_scadenza__lte=soglia,
        ).select_related('lavoratore__azienda').order_by('data_scadenza')

        context = {
            'aziende': Azienda.objects.all().order_by('ragione_sociale'),
            'totale_aziende': Azienda.objects.count(),
            'totale_lavoratori': Lavoratore.objects.filter(attivo=True).count(),
            'scadenze_imminenti': scadenze_imminenti,
            'totale_scadenze': scadenze_imminenti.count(),
        }
        return render(request, 'aziende/admin_dashboard.html', context)


class AdminAggiornaContrattoView(AdminRequiredMixin, View):
    def post(self, request, pk):
        azienda = get_object_or_404(Azienda, pk=pk)
        valore = request.POST.get('contratto_saldato')
        if valore in ('1', 'true', 'True', 'on'):
            azienda.contratto_saldato = True
        elif valore in ('0', 'false', 'False'):
            azienda.contratto_saldato = False
        else:
            azienda.contratto_saldato = not azienda.contratto_saldato
        azienda.save(update_fields=['contratto_saldato'])
        messages.success(request, f'Contratto aggiornato per {azienda.ragione_sociale}.')
        return redirect('admin_dashboard')


class AdminCreaAziendaView(AdminRequiredMixin, View):
    def get(self, request):
        return render(request, 'aziende/admin_crea_azienda.html', {
            'form': CreaAziendaForm()
        })

    def post(self, request):
        form = CreaAziendaForm(request.POST, request.FILES)
        if form.is_valid():
            # Crea utente
            user = CustomUser.objects.create_user(
                email=form.cleaned_data['email'],
                password=form.cleaned_data['password'],
                role=CustomUser.AZIENDA
            )
            # Crea azienda collegata
            Azienda.objects.create(
                user=user,
                ragione_sociale=form.cleaned_data['ragione_sociale'],
                codice_univoco=form.cleaned_data['codice_univoco'],
                logo_azienda=form.cleaned_data['logo_azienda'],
                pec=form.cleaned_data['pec'],
                referente_azienda=form.cleaned_data['referente_azienda'],
                codice_fiscale=form.cleaned_data['codice_fiscale'],
                partita_iva=form.cleaned_data['partita_iva'],
                email_contatto=form.cleaned_data['email_contatto'],
                telefono=form.cleaned_data['telefono'],
                condizioni_pagamento_riservate=form.cleaned_data['condizioni_pagamento_riservate'],
                protocollo_sanitario=form.cleaned_data['protocollo_sanitario'],
                nomina_medico=form.cleaned_data['nomina_medico'],
                verbali_sopralluogo=form.cleaned_data['verbali_sopralluogo'],
                varie_documento=form.cleaned_data.get('varie_documento'),
                varie_note=form.cleaned_data.get('varie_note', ''),
            )
            messages.success(request, f'Azienda {form.cleaned_data["ragione_sociale"]} creata con successo.')
            return redirect('admin_dashboard')
        return render(request, 'aziende/admin_crea_azienda.html', {'form': form})


class AdminLavoratoriView(AdminRequiredMixin, View):
    def get(self, request):
        lavoratori = Lavoratore.objects.select_related('azienda', 'sede').filter(attivo=True)
        
        # Filtro opzionale per azienda
        azienda_pk = request.GET.get('azienda')
        azienda_selezionata = None
        if azienda_pk:
            azienda_selezionata = get_object_or_404(Azienda, pk=azienda_pk)
            lavoratori = lavoratori.filter(azienda=azienda_selezionata)

        lavoratori = lavoratori.order_by('azienda', 'cognome')
        return render(request, 'aziende/admin_lavoratori.html', {
            'lavoratori': lavoratori,
            'azienda_selezionata': azienda_selezionata,
        })


class AdminLavoratoreDetailView(AdminRequiredMixin, View):
    def get(self, request, pk):
        lavoratore = get_object_or_404(Lavoratore, pk=pk)
        cartella, _ = CartellaClinica.objects.get_or_create(lavoratore=lavoratore)
        esiti = EsitoIdoneita.objects.filter(lavoratore=lavoratore).order_by('-data_visita')
        documenti = cartella.documenti.order_by('-data')
        return render(request, 'aziende/admin_lavoratore_detail.html', {
            'lavoratore': lavoratore,
            'cartella': cartella,
            'esiti': esiti,
            'documenti': documenti,
            'doc_form': DocumentoSanitarioForm(),
            'esito_form': EsitoIdoneitaForm(),
        })


class AdminCaricaDocumentoView(AdminRequiredMixin, View):
    def post(self, request, pk):
        lavoratore = get_object_or_404(Lavoratore, pk=pk)
        cartella, _ = CartellaClinica.objects.get_or_create(lavoratore=lavoratore)
        form = DocumentoSanitarioForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.cartella = cartella
            doc.save()
            messages.success(request, 'Documento caricato con successo.')
            if doc.tipo == DocumentoSanitario.REFERTO and getattr(lavoratore, 'user', None):
                subject = 'I suoi referti sono disponibili — Centro Medico Delta'
                corpo = (
                    "Gentile,\n"
                    "Le comunichiamo che Centro Medico Delta ha caricato sulla piattaforma i referti relativi alla sua visita medica.\n"
                    "Può consultarli in qualsiasi momento accedendo alla sua area personale.\n"
                    "Per qualsiasi informazione, rimaniamo a sua disposizione.\n"
                    "Cordiali saluti,\n"
                    "Centro Medico Delta"
                )
                send_notification_email(subject, corpo, [lavoratore.user.email])
        else:
            messages.error(request, 'Errore nel caricamento del documento.')
        return redirect('admin_lavoratore_detail', pk=pk)


class AdminRegistraEsitoView(AdminRequiredMixin, View):
    def post(self, request, pk):
        lavoratore = get_object_or_404(Lavoratore, pk=pk)
        form = EsitoIdoneitaForm(request.POST, request.FILES)
        if form.is_valid():
            esito = form.save(commit=False)
            esito.lavoratore = lavoratore
            esito.save()
            azienda = lavoratore.azienda
            destinatario = azienda.user.email if getattr(azienda, 'user', None) else azienda.email_contatto
            subject = 'Idoneità alla mansione disponibile'
            corpo = (
                "Gentile,\n"
                f"Le comunichiamo che Centro Medico Delta ha caricato sulla piattaforma il giudizio di idoneità alla mansione relativo al lavoratore {lavoratore.nome_completo}.\n"
                "Il documento è ora consultabile accedendo alla sua area riservata.\n"
                "[ ACCEDI ALLA PIATTAFORMA ]\n"
                "Per qualsiasi informazione, rimaniamo a sua disposizione.\n"
                "Cordiali saluti,\n"
                "Centro Medico Delta"
            )
            send_notification_email(subject, corpo, [destinatario])
            messages.success(request, 'Esito idoneità registrato.')
        else:
            messages.error(request, 'Errore nella registrazione dell\'esito.')
        return redirect('admin_lavoratore_detail', pk=pk)


# ─── AZIENDA ──────────────────────────────────────────────────────────────────

class AziendaDashboardView(AziendaRequiredMixin, View):
    def get(self, request):
        azienda = getattr(request, 'azienda', None) or get_object_or_404(Azienda, user=request.user)
        lavoratori = Lavoratore.objects.filter(
            azienda=azienda, attivo=True
        ).order_by('cognome')
        context = {
            'azienda': azienda,
            'lavoratori': lavoratori,
            'totale_lavoratori': lavoratori.count(),
            'centro_delta_contact': CENTRO_DELTA_CONTACT,
        }
        return render(request, 'aziende/azienda_dashboard.html', context)


class AziendaLavoratoreCreateView(AziendaRequiredMixin, View):
    def get(self, request):
        azienda = getattr(request, 'azienda', None) or get_object_or_404(Azienda, user=request.user)
        form = LavoratoreForm(azienda=azienda, include_account_fields=True)
        return render(request, 'aziende/azienda_lavoratore_form.html', {
            'form': form, 'azienda': azienda, 'action': 'Nuovo lavoratore'
        })

    def post(self, request):
        azienda = getattr(request, 'azienda', None) or get_object_or_404(Azienda, user=request.user)
        form = LavoratoreForm(request.POST, azienda=azienda, include_account_fields=True)
        if form.is_valid():
            lavoratore = form.save(commit=False)
            lavoratore.azienda = azienda
            account_email = form.cleaned_data.get('account_email')
            account_password = form.cleaned_data.get('account_password')
            if account_email and account_password:
                user = CustomUser.objects.create_user(
                    email=account_email,
                    password=account_password,
                    role=CustomUser.OPERATORE,
                )
                lavoratore.user = user
            lavoratore.save()
            messages.success(request, f'{lavoratore.nome_completo} aggiunto con successo.')
            return redirect('azienda_dashboard')
        return render(request, 'aziende/azienda_lavoratore_form.html', {
            'form': form, 'azienda': azienda, 'action': 'Nuovo lavoratore'
        })


class AziendaLavoratoreEditView(AziendaRequiredMixin, View):
    def get(self, request, pk):
        azienda = getattr(request, 'azienda', None) or get_object_or_404(Azienda, user=request.user)
        lavoratore = get_object_or_404(Lavoratore, pk=pk, azienda=azienda)
        form = LavoratoreForm(instance=lavoratore, azienda=azienda)
        return render(request, 'aziende/azienda_lavoratore_form.html', {
            'form': form, 'azienda': azienda, 'action': 'Modifica lavoratore'
        })

    def post(self, request, pk):
        azienda = getattr(request, 'azienda', None) or get_object_or_404(Azienda, user=request.user)
        lavoratore = get_object_or_404(Lavoratore, pk=pk, azienda=azienda)
        form = LavoratoreForm(request.POST, instance=lavoratore, azienda=azienda)
        if form.is_valid():
            form.save()
            messages.success(request, 'Lavoratore aggiornato.')
            return redirect('azienda_dashboard')
        return render(request, 'aziende/azienda_lavoratore_form.html', {
            'form': form, 'azienda': azienda, 'action': 'Modifica lavoratore'
        })


class AziendaLavoratoreDetailView(AziendaRequiredMixin, View):
    def get(self, request, pk):
        azienda = getattr(request, 'azienda', None) or get_object_or_404(Azienda, user=request.user)
        lavoratore = get_object_or_404(Lavoratore, pk=pk, azienda=azienda)
        esiti = EsitoIdoneita.objects.filter(lavoratore=lavoratore).order_by('-data_visita')
        return render(request, 'aziende/azienda_lavoratore.html', {
            'lavoratore': lavoratore,
            'esiti': esiti,
        })


# ─── OPERATORE ────────────────────────────────────────────────────────────────

class OperatoreDashboardView(OperatoreRequiredMixin, View):
    def get(self, request):
        lavoratore = get_object_or_404(Lavoratore, user=request.user)
        cartella = getattr(lavoratore, 'cartella', None)
        esiti = EsitoIdoneita.objects.filter(lavoratore=lavoratore).order_by('-data_visita')
        documenti = cartella.documenti.order_by('-data') if cartella else []
        return render(request, 'aziende/operatore_dashboard.html', {
            'lavoratore': lavoratore,
            'cartella': cartella,
            'esiti': esiti,
            'documenti': documenti,
        })
    
