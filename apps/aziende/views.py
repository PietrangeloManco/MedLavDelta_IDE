import logging
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.db.models import Count, OuterRef, Subquery
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from apps.accounts.listing import apply_sorting, apply_text_search, get_list_search_term
from apps.accounts.mixins import (
    AdminPermissionRequiredMixin,
    AziendaRequiredMixin,
    OperatoreRequiredMixin,
)
from apps.accounts.models import CustomUser
from apps.accounts.services import create_user_with_generated_password
from apps.sanitaria.forms import DocumentoSanitarioForm, EsitoIdoneitaForm
from apps.sanitaria.models import CartellaClinica, DocumentoSanitario, EsitoIdoneita

from .forms import CreaAziendaForm, DocumentoAziendaleForm, LavoratoreForm
from .models import Azienda, DocumentoAziendale, Lavoratore

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


def get_azienda_documenti_context(azienda):
    return {
        'documenti_iniziali': azienda.get_documenti_iniziali(),
        'documenti_aggiuntivi': azienda.documenti_generici.select_related('caricato_da'),
    }


def create_lavoratore_with_optional_account(form, azienda, request=None):
    lavoratore = form.save(commit=False)
    lavoratore.azienda = azienda
    account_email = form.cleaned_data.get('account_email')
    if account_email:
        user, _temporary_password = create_user_with_generated_password(
            email=account_email,
            role=CustomUser.OPERATORE,
            request=request,
        )
        lavoratore.user = user
    lavoratore.save()
    return lavoratore


def can_admin_manage_workers(user):
    return user.has_admin_permission(CustomUser.ADMIN_PERMISSION_WORKERS) or user.has_admin_permission(
        CustomUser.ADMIN_PERMISSION_COMPANIES
    )


def with_latest_worker_status(queryset):
    latest_outcome = EsitoIdoneita.objects.filter(lavoratore=OuterRef('pk')).order_by('-data_visita')
    return queryset.annotate(
        ultimo_esito=Subquery(latest_outcome.values('esito')[:1]),
        ultima_scadenza=Subquery(latest_outcome.values('data_scadenza')[:1]),
    )


class AdminDashboardView(AdminPermissionRequiredMixin, View):
    admin_permissions_required = (CustomUser.ADMIN_PERMISSION_DASHBOARD,)

    def get(self, request):
        oggi = timezone.now().date()
        soglia = oggi + timedelta(days=30)

        scadenze_imminenti = EsitoIdoneita.objects.filter(
            data_scadenza__gte=oggi,
            data_scadenza__lte=soglia,
        ).select_related('lavoratore__azienda').order_by('data_scadenza')

        context = {
            'totale_aziende': Azienda.objects.count(),
            'totale_lavoratori': Lavoratore.objects.filter(attivo=True).count(),
            'scadenze_imminenti': scadenze_imminenti,
            'totale_scadenze': scadenze_imminenti.count(),
        }
        return render(request, 'aziende/admin_dashboard.html', context)


class AdminAziendeListView(AdminPermissionRequiredMixin, View):
    admin_permissions_required = (
        CustomUser.ADMIN_PERMISSION_COMPANIES,
        CustomUser.ADMIN_PERMISSION_COMPANY_DOCUMENTS,
        CustomUser.ADMIN_PERMISSION_PREVENTIVI,
        CustomUser.ADMIN_PERMISSION_FATTURE,
    )
    admin_permissions_mode = 'any'

    def get(self, request):
        aziende = Azienda.objects.annotate(lavoratori_totali=Count('lavoratori', distinct=True))
        current_search = get_list_search_term(request)
        aziende = apply_text_search(
            aziende,
            current_search,
            (
                'ragione_sociale',
                'partita_iva',
                'email_contatto',
                'codice_univoco',
                'pec',
                'referente_azienda',
            ),
        )
        aziende, current_sort, current_dir = apply_sorting(
            aziende,
            sort_key=request.GET.get('sort'),
            direction=request.GET.get('dir'),
            sort_map={
                'ragione_sociale': ('ragione_sociale',),
                'partita_iva': ('partita_iva', 'ragione_sociale'),
                'email': ('email_contatto', 'ragione_sociale'),
                'lavoratori': ('lavoratori_totali', 'ragione_sociale'),
                'contratto': ('contratto_saldato', 'ragione_sociale'),
            },
            default_sort='ragione_sociale',
        )
        return render(request, 'aziende/admin_aziende_list.html', {
            'aziende': aziende,
            'current_search': current_search,
            'current_sort': current_sort,
            'current_dir': current_dir,
        })


class AdminAziendaDetailView(AdminPermissionRequiredMixin, View):
    admin_permissions_required = (
        CustomUser.ADMIN_PERMISSION_COMPANIES,
        CustomUser.ADMIN_PERMISSION_COMPANY_DOCUMENTS,
    )
    admin_permissions_mode = 'any'

    def get(self, request, pk):
        azienda = get_object_or_404(Azienda, pk=pk)
        context = {
            'azienda': azienda,
            'lavoratori': azienda.lavoratori.filter(attivo=True).order_by('cognome', 'nome'),
            'document_form': DocumentoAziendaleForm(),
            'can_manage_company': request.user.has_admin_permission(
                CustomUser.ADMIN_PERMISSION_COMPANIES
            ),
            'can_upload_documents': request.user.has_admin_permission(
                CustomUser.ADMIN_PERMISSION_COMPANY_DOCUMENTS
            ),
            'can_manage_workers': can_admin_manage_workers(request.user),
            **get_azienda_documenti_context(azienda),
        }
        return render(request, 'aziende/admin_azienda_detail.html', context)


class AdminAggiornaContrattoView(AdminPermissionRequiredMixin, View):
    admin_permissions_required = (CustomUser.ADMIN_PERMISSION_COMPANIES,)

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
        next_url = request.POST.get('next')
        if next_url:
            return redirect(next_url)
        return redirect('admin_azienda_detail', pk=pk)


class AdminCreaAziendaView(AdminPermissionRequiredMixin, View):
    admin_permissions_required = (CustomUser.ADMIN_PERMISSION_COMPANIES,)

    def get(self, request):
        return render(request, 'aziende/admin_crea_azienda.html', {
            'form': CreaAziendaForm(),
        })

    def post(self, request):
        form = CreaAziendaForm(request.POST, request.FILES)
        if form.is_valid():
            user, _temporary_password = create_user_with_generated_password(
                email=form.cleaned_data['email'],
                role=CustomUser.AZIENDA,
                request=request,
            )
            azienda = Azienda.objects.create(
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
            messages.success(
                request,
                f'Azienda {form.cleaned_data["ragione_sociale"]} creata con successo.',
            )
            return redirect('admin_azienda_detail', pk=azienda.pk)
        return render(request, 'aziende/admin_crea_azienda.html', {'form': form})


class AdminCaricaDocumentoAziendaleView(AdminPermissionRequiredMixin, View):
    admin_permissions_required = (CustomUser.ADMIN_PERMISSION_COMPANY_DOCUMENTS,)

    def post(self, request, pk):
        azienda = get_object_or_404(Azienda, pk=pk)
        form = DocumentoAziendaleForm(request.POST, request.FILES)
        if form.is_valid():
            documento = form.save(commit=False)
            documento.azienda = azienda
            documento.origine = DocumentoAziendale.ORIGINE_ADMIN
            documento.caricato_da = request.user
            documento.save()
            messages.success(request, 'Documento aziendale caricato con successo.')
        else:
            messages.error(request, 'Errore nel caricamento del documento aziendale.')
        return redirect('admin_azienda_detail', pk=pk)


class AdminLavoratoriView(AdminPermissionRequiredMixin, View):
    admin_permissions_required = (
        CustomUser.ADMIN_PERMISSION_WORKERS,
        CustomUser.ADMIN_PERMISSION_MEDICAL_RECORDS,
    )
    admin_permissions_mode = 'any'

    def get(self, request):
        lavoratori = with_latest_worker_status(
            Lavoratore.objects.select_related('azienda', 'sede').filter(attivo=True)
        )
        azienda_pk = request.GET.get('azienda')
        azienda_selezionata = None
        if azienda_pk:
            azienda_selezionata = get_object_or_404(Azienda, pk=azienda_pk)
            lavoratori = lavoratori.filter(azienda=azienda_selezionata)

        current_search = get_list_search_term(request)
        lavoratori = apply_text_search(
            lavoratori,
            current_search,
            (
                'nome',
                'cognome',
                'codice_fiscale',
                'azienda__ragione_sociale',
                'sede__nome',
                'mansione',
            ),
        )
        lavoratori, current_sort, current_dir = apply_sorting(
            lavoratori,
            sort_key=request.GET.get('sort'),
            direction=request.GET.get('dir'),
            sort_map={
                'nominativo': ('cognome', 'nome'),
                'azienda': ('azienda__ragione_sociale', 'cognome', 'nome'),
                'sede': ('sede__nome', 'cognome', 'nome'),
                'mansione': ('mansione', 'cognome', 'nome'),
                'esito': ('ultimo_esito', 'cognome', 'nome'),
                'scadenza': ('ultima_scadenza', 'cognome', 'nome'),
            },
            default_sort='nominativo',
        )
        return render(request, 'aziende/admin_lavoratori.html', {
            'lavoratori': lavoratori,
            'aziende': Azienda.objects.order_by('ragione_sociale'),
            'azienda_selezionata': azienda_selezionata,
            'current_search': current_search,
            'current_sort': current_sort,
            'current_dir': current_dir,
            'today': timezone.localdate(),
        })


class AdminAziendaLavoratoreCreateView(AdminPermissionRequiredMixin, View):
    admin_permissions_required = (
        CustomUser.ADMIN_PERMISSION_WORKERS,
        CustomUser.ADMIN_PERMISSION_COMPANIES,
    )
    admin_permissions_mode = 'any'

    def get(self, request, pk):
        azienda = get_object_or_404(Azienda, pk=pk)
        form = LavoratoreForm(azienda=azienda, include_account_fields=True)
        return render(request, 'aziende/azienda_lavoratore_form.html', {
            'form': form,
            'azienda': azienda,
            'action': 'Nuovo lavoratore',
            'is_admin_context': True,
            'back_href': reverse('admin_azienda_detail', args=[azienda.pk]),
            'back_label': 'Torna alla scheda azienda',
        })

    def post(self, request, pk):
        azienda = get_object_or_404(Azienda, pk=pk)
        form = LavoratoreForm(request.POST, azienda=azienda, include_account_fields=True)
        if form.is_valid():
            lavoratore = create_lavoratore_with_optional_account(form, azienda, request=request)
            messages.success(request, f'{lavoratore.nome_completo} aggiunto con successo.')
            return redirect('admin_azienda_detail', pk=azienda.pk)
        return render(request, 'aziende/azienda_lavoratore_form.html', {
            'form': form,
            'azienda': azienda,
            'action': 'Nuovo lavoratore',
            'is_admin_context': True,
            'back_href': reverse('admin_azienda_detail', args=[azienda.pk]),
            'back_label': 'Torna alla scheda azienda',
        })


class AdminLavoratoreEditView(AdminPermissionRequiredMixin, View):
    admin_permissions_required = (
        CustomUser.ADMIN_PERMISSION_WORKERS,
        CustomUser.ADMIN_PERMISSION_COMPANIES,
    )
    admin_permissions_mode = 'any'

    def get(self, request, pk):
        lavoratore = get_object_or_404(Lavoratore, pk=pk)
        form = LavoratoreForm(instance=lavoratore, azienda=lavoratore.azienda)
        return render(request, 'aziende/azienda_lavoratore_form.html', {
            'form': form,
            'azienda': lavoratore.azienda,
            'action': 'Modifica lavoratore',
            'is_admin_context': True,
            'back_href': reverse('admin_lavoratore_detail', args=[lavoratore.pk]),
            'back_label': 'Torna alla scheda lavoratore',
        })

    def post(self, request, pk):
        lavoratore = get_object_or_404(Lavoratore, pk=pk)
        form = LavoratoreForm(request.POST, instance=lavoratore, azienda=lavoratore.azienda)
        if form.is_valid():
            form.save()
            messages.success(request, 'Lavoratore aggiornato.')
            return redirect('admin_lavoratore_detail', pk=lavoratore.pk)
        return render(request, 'aziende/azienda_lavoratore_form.html', {
            'form': form,
            'azienda': lavoratore.azienda,
            'action': 'Modifica lavoratore',
            'is_admin_context': True,
            'back_href': reverse('admin_lavoratore_detail', args=[lavoratore.pk]),
            'back_label': 'Torna alla scheda lavoratore',
        })


class AdminLavoratoreDetailView(AdminPermissionRequiredMixin, View):
    admin_permissions_required = (CustomUser.ADMIN_PERMISSION_MEDICAL_RECORDS,)

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
            'can_edit_worker': can_admin_manage_workers(request.user),
        })


class AdminCaricaDocumentoView(AdminPermissionRequiredMixin, View):
    admin_permissions_required = (CustomUser.ADMIN_PERMISSION_MEDICAL_RECORDS,)

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
                subject = 'I tuoi referti sono disponibili su MedLavDelta'
                corpo = (
                    "Gentile,\n"
                    "Le comunichiamo che Centro Delta ha caricato sulla piattaforma MedLavDelta "
                    "i referti relativi alla sua visita medica.\n"
                    "Può consultarli in qualsiasi momento accedendo alla sua area personale.\n"
                    "Per qualsiasi informazione, rimaniamo a sua disposizione.\n"
                    "Cordiali saluti,\n"
                    "Centro Delta"
                )
                send_notification_email(subject, corpo, [lavoratore.user.email])
        else:
            messages.error(request, 'Errore nel caricamento del documento.')
        return redirect('admin_lavoratore_detail', pk=pk)


class AdminRegistraEsitoView(AdminPermissionRequiredMixin, View):
    admin_permissions_required = (CustomUser.ADMIN_PERMISSION_MEDICAL_RECORDS,)

    def post(self, request, pk):
        lavoratore = get_object_or_404(Lavoratore, pk=pk)
        form = EsitoIdoneitaForm(request.POST, request.FILES)
        if form.is_valid():
            esito = form.save(commit=False)
            esito.lavoratore = lavoratore
            esito.save()
            azienda = lavoratore.azienda
            destinatario = (
                azienda.user.email
                if getattr(azienda, 'user', None)
                else azienda.email_contatto
            )
            subject = 'Giudizio di idoneità disponibile su MedLavDelta'
            corpo = (
                "Gentile,\n"
                "Le comunichiamo che Centro Delta ha caricato sulla piattaforma MedLavDelta "
                f"il giudizio di idoneità alla mansione relativo al lavoratore {lavoratore.nome_completo}.\n"
                "Il documento è ora consultabile accedendo alla sua area riservata.\n"
                "[ ACCEDI ALLA PIATTAFORMA ]\n"
                "Per qualsiasi informazione, rimaniamo a sua disposizione.\n"
                "Cordiali saluti,\n"
                "Centro Delta"
            )
            send_notification_email(subject, corpo, [destinatario])
            messages.success(request, 'Esito idoneità registrato.')
        else:
            messages.error(request, "Errore nella registrazione dell'esito.")
        return redirect('admin_lavoratore_detail', pk=pk)


class AziendaDashboardView(AziendaRequiredMixin, View):
    def get(self, request):
        azienda = getattr(request, 'azienda', None) or get_object_or_404(Azienda, user=request.user)
        lavoratori = with_latest_worker_status(
            Lavoratore.objects.filter(
                azienda=azienda,
                attivo=True,
            ).select_related('sede')
        )
        current_search = get_list_search_term(request)
        lavoratori = apply_text_search(
            lavoratori,
            current_search,
            (
                'nome',
                'cognome',
                'codice_fiscale',
                'sede__nome',
                'mansione',
            ),
        )
        lavoratori, current_sort, current_dir = apply_sorting(
            lavoratori,
            sort_key=request.GET.get('sort'),
            direction=request.GET.get('dir'),
            sort_map={
                'nominativo': ('cognome', 'nome'),
                'mansione': ('mansione', 'cognome', 'nome'),
                'sede': ('sede__nome', 'cognome', 'nome'),
                'esito': ('ultimo_esito', 'cognome', 'nome'),
                'scadenza': ('ultima_scadenza', 'cognome', 'nome'),
            },
            default_sort='nominativo',
        )
        context = {
            'azienda': azienda,
            'lavoratori': lavoratori,
            'totale_lavoratori': Lavoratore.objects.filter(azienda=azienda, attivo=True).count(),
            'totale_documenti_aggiuntivi': azienda.documenti_generici.count(),
            'centro_delta_contact': CENTRO_DELTA_CONTACT,
            'current_search': current_search,
            'current_sort': current_sort,
            'current_dir': current_dir,
            'today': timezone.localdate(),
        }
        return render(request, 'aziende/azienda_dashboard.html', context)


class AziendaDocumentiView(AziendaRequiredMixin, View):
    def get(self, request):
        azienda = getattr(request, 'azienda', None) or get_object_or_404(Azienda, user=request.user)
        context = {
            'azienda': azienda,
            'document_form': DocumentoAziendaleForm(),
            **get_azienda_documenti_context(azienda),
        }
        return render(request, 'aziende/azienda_documenti.html', context)


class AziendaCaricaDocumentoView(AziendaRequiredMixin, View):
    def post(self, request):
        azienda = getattr(request, 'azienda', None) or get_object_or_404(Azienda, user=request.user)
        form = DocumentoAziendaleForm(request.POST, request.FILES)
        if form.is_valid():
            documento = form.save(commit=False)
            documento.azienda = azienda
            documento.origine = DocumentoAziendale.ORIGINE_AZIENDA
            documento.caricato_da = request.user
            documento.save()
            messages.success(request, 'Documento caricato con successo.')
        else:
            messages.error(request, 'Errore nel caricamento del documento.')
        return redirect('azienda_documenti')


class AziendaLavoratoreCreateView(AziendaRequiredMixin, View):
    def get(self, request):
        azienda = getattr(request, 'azienda', None) or get_object_or_404(Azienda, user=request.user)
        form = LavoratoreForm(azienda=azienda, include_account_fields=True)
        return render(request, 'aziende/azienda_lavoratore_form.html', {
            'form': form,
            'azienda': azienda,
            'action': 'Nuovo lavoratore',
            'back_href': reverse('azienda_dashboard'),
            'back_label': 'Torna alla lista',
        })

    def post(self, request):
        azienda = getattr(request, 'azienda', None) or get_object_or_404(Azienda, user=request.user)
        form = LavoratoreForm(request.POST, azienda=azienda, include_account_fields=True)
        if form.is_valid():
            lavoratore = create_lavoratore_with_optional_account(form, azienda, request=request)
            messages.success(request, f'{lavoratore.nome_completo} aggiunto con successo.')
            return redirect('azienda_dashboard')
        return render(request, 'aziende/azienda_lavoratore_form.html', {
            'form': form,
            'azienda': azienda,
            'action': 'Nuovo lavoratore',
            'back_href': reverse('azienda_dashboard'),
            'back_label': 'Torna alla lista',
        })


class AziendaLavoratoreEditView(AziendaRequiredMixin, View):
    def get(self, request, pk):
        azienda = getattr(request, 'azienda', None) or get_object_or_404(Azienda, user=request.user)
        lavoratore = get_object_or_404(Lavoratore, pk=pk, azienda=azienda)
        form = LavoratoreForm(instance=lavoratore, azienda=azienda)
        return render(request, 'aziende/azienda_lavoratore_form.html', {
            'form': form,
            'azienda': azienda,
            'action': 'Modifica lavoratore',
            'back_href': reverse('azienda_dashboard'),
            'back_label': 'Torna alla lista',
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
            'form': form,
            'azienda': azienda,
            'action': 'Modifica lavoratore',
            'back_href': reverse('azienda_dashboard'),
            'back_label': 'Torna alla lista',
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
