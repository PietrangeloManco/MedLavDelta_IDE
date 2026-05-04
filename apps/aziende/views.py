from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.db.models import Case, Count, IntegerField, OuterRef, Subquery, Value, When
from django.http import FileResponse, Http404
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
from apps.sanitaria.forms import DocumentoSanitarioForm, EsitoIdoneitaForm, EsitoScadenzaForm, validate_document_upload
from apps.sanitaria.models import CartellaClinica, DocumentoSanitario, EsitoIdoneita

from .forms import (
    AziendaNotificationCcForm,
    CreaAccountAziendaReadOnlyForm,
    CreaAccountLavoratoreForm,
    CreaAziendaForm,
    DocumentoAziendaleForm,
    LavoratoreForm,
    ReplaceFileForm,
)
from .models import Azienda, AziendaReadOnlyAccess, DocumentoAziendale, Lavoratore
from .services import (
    send_company_notification_email,
    send_new_company_created_notification,
    send_new_worker_created_notification,
    send_platform_email,
)
from .validators import (
    COMPANY_DOCUMENT_MAX_UPLOAD_SIZE,
    COMPANY_LOGO_MAX_UPLOAD_SIZE,
    validate_company_document_upload,
    validate_company_logo_upload,
)

CENTRO_DELTA_CONTACT = {
    'nome': 'Cocozza Rosanna',
    'email': 'rosanna.cocozza@tecnobios.com',
    'telefono': '351 6572647',
    'ruolo': 'Referente Centro Delta',
}
ADMIN_STAFF_GUIDE_FILENAME = 'Guida_Interna_Staff_CentroDelta_rev020426.pdf'
ADMIN_STAFF_GUIDE_PATH = settings.BASE_DIR / 'static' / 'guides' / ADMIN_STAFF_GUIDE_FILENAME
COMPANY_GUIDE_FILENAME = 'Guida_Aziende_CentroDelt_rev200426.pdf'
COMPANY_GUIDE_PATH = settings.BASE_DIR / 'static' / 'guides' / COMPANY_GUIDE_FILENAME


def get_azienda_documenti_context(azienda):
    return {
        'documenti_iniziali': azienda.get_documenti_iniziali(),
        'documenti_aggiuntivi': azienda.documenti_generici.select_related('caricato_da'),
    }


def add_form_errors_message(request, form, default_message):
    errors = []
    for field_name, field_errors in form.errors.items():
        label = ''
        if field_name in form.fields:
            label = form.fields[field_name].label
        for error in field_errors:
            errors.append(f'{label}: {error}' if label else str(error))
    if errors:
        messages.error(request, ' '.join(errors))
        return
    messages.error(request, default_message)


def replace_model_file(instance, field_name, uploaded_file, *, extra_updates=None):
    extra_updates = extra_updates or []
    field = instance._meta.get_field(field_name)
    current_file = getattr(instance, field_name)
    previous_name = current_file.name if current_file else ''
    setattr(instance, field_name, uploaded_file)
    instance.save(update_fields=[field_name, *extra_updates])
    updated_file = getattr(instance, field_name)
    updated_name = updated_file.name if updated_file else ''
    if previous_name and previous_name != updated_name:
        field.storage.delete(previous_name)


def build_replace_file_form(
    post_data=None,
    files_data=None,
    *,
    validator,
    file_help_text,
    accept,
    include_note=False,
    note_initial='',
    note_label='Note',
):
    return ReplaceFileForm(
        post_data,
        files_data,
        validator=validator,
        file_help_text=file_help_text,
        accept=accept,
        include_note=include_note,
        note_initial=note_initial,
        note_label=note_label,
    )


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
    send_new_worker_created_notification(lavoratore, request=request)
    return lavoratore


def create_account_for_lavoratore(lavoratore, account_email, request=None):
    user, _temporary_password = create_user_with_generated_password(
        email=account_email,
        role=CustomUser.OPERATORE,
        request=request,
    )
    lavoratore.user = user
    lavoratore.save(update_fields=['user'])
    return user


def get_lavoratore_create_success_message(lavoratore):
    if lavoratore.user_id:
        return f'{lavoratore.nome_completo} aggiunto con successo.'
    return (
        f"{lavoratore.nome_completo} aggiunto con successo senza account. "
        "Potrai creare l'account in seguito dalla scheda lavoratore."
    )


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


def get_admin_lavoratore_detail_context(request, lavoratore, *, account_form=None):
    cartella, _ = CartellaClinica.objects.get_or_create(lavoratore=lavoratore)
    esiti = EsitoIdoneita.objects.filter(lavoratore=lavoratore).order_by('-data_visita')
    documenti = cartella.documenti.order_by('-data')
    return {
        'lavoratore': lavoratore,
        'cartella': cartella,
        'esiti': esiti,
        'documenti': documenti,
        'doc_form': DocumentoSanitarioForm(),
        'esito_form': EsitoIdoneitaForm(),
        'account_form': account_form or CreaAccountLavoratoreForm(lavoratore=lavoratore),
        'can_edit_worker': can_admin_manage_workers(request.user),
        'can_manage_account': can_admin_manage_workers(request.user),
    }


def get_azienda_lavoratore_detail_context(lavoratore, *, account_form=None):
    esiti = EsitoIdoneita.objects.filter(lavoratore=lavoratore).order_by('-data_visita')
    return {
        'lavoratore': lavoratore,
        'esiti': esiti,
        'account_form': account_form or CreaAccountLavoratoreForm(lavoratore=lavoratore),
    }


def get_admin_azienda_detail_context(request, azienda, *, notification_cc_form=None):
    return {
        'azienda': azienda,
        'lavoratori': azienda.lavoratori.filter(attivo=True).order_by('cognome', 'nome'),
        'document_form': DocumentoAziendaleForm(),
        'notification_cc_form': notification_cc_form or AziendaNotificationCcForm(initial={
            'email_notifiche_cc': azienda.formatted_notification_cc_emails,
        }),
        'read_only_accounts': azienda.read_only_accesses.select_related('user', 'created_by'),
        'can_manage_company': request.user.has_admin_permission(
            CustomUser.ADMIN_PERMISSION_COMPANIES
        ),
        'can_upload_documents': request.user.has_admin_permission(
            CustomUser.ADMIN_PERMISSION_COMPANY_DOCUMENTS
        ),
        'can_manage_workers': can_admin_manage_workers(request.user),
        **get_azienda_documenti_context(azienda),
    }


def get_azienda_dashboard_context(request, azienda, *, read_only_account_form=None):
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
    return {
        'azienda': azienda,
        'lavoratori': lavoratori,
        'totale_lavoratori': Lavoratore.objects.filter(azienda=azienda, attivo=True).count(),
        'totale_documenti_aggiuntivi': azienda.documenti_generici.count(),
        'centro_delta_contact': CENTRO_DELTA_CONTACT,
        'read_only_accounts': azienda.read_only_accesses.select_related('user', 'created_by'),
        'read_only_account_form': read_only_account_form or CreaAccountAziendaReadOnlyForm(
            azienda=azienda,
        ),
        'current_search': current_search,
        'current_sort': current_sort,
        'current_dir': current_dir,
        'today': timezone.localdate(),
    }


def create_read_only_account_for_azienda(azienda, account_email, request=None):
    user, _temporary_password = create_user_with_generated_password(
        email=account_email,
        role=CustomUser.AZIENDA,
        request=request,
    )
    return AziendaReadOnlyAccess.objects.create(
        azienda=azienda,
        user=user,
        created_by=getattr(request, 'user', None) if request else None,
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


class AdminStaffGuideView(AdminPermissionRequiredMixin, View):
    admin_permissions_required = (CustomUser.ADMIN_PERMISSION_DASHBOARD,)

    def get(self, request):
        if not ADMIN_STAFF_GUIDE_PATH.exists():
            raise Http404('Guida staff non disponibile.')

        response = FileResponse(
            ADMIN_STAFF_GUIDE_PATH.open('rb'),
            content_type='application/pdf',
        )
        response['Content-Disposition'] = f'inline; filename="{ADMIN_STAFF_GUIDE_FILENAME}"'
        return response


class AdminAziendeListView(AdminPermissionRequiredMixin, View):
    admin_permissions_required = (
        CustomUser.ADMIN_PERMISSION_COMPANIES,
        CustomUser.ADMIN_PERMISSION_COMPANY_DOCUMENTS,
        CustomUser.ADMIN_PERMISSION_PREVENTIVI,
        CustomUser.ADMIN_PERMISSION_FATTURE,
    )
    admin_permissions_mode = 'any'

    def get(self, request):
        aziende = Azienda.objects.annotate(
            lavoratori_totali=Count('lavoratori', distinct=True),
            contratto_ordinamento=Case(
                When(stato_contratto=Azienda.CONTRATTO_SALDATO, then=Value(0)),
                When(
                    stato_contratto=Azienda.CONTRATTO_IN_ATTESA_PAGAMENTO,
                    then=Value(1),
                ),
                default=Value(2),
                output_field=IntegerField(),
            ),
        )
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
                'contratto': ('contratto_ordinamento', 'ragione_sociale'),
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
        return render(
            request,
            'aziende/admin_azienda_detail.html',
            get_admin_azienda_detail_context(request, azienda),
        )


class AdminAggiornaContrattoView(AdminPermissionRequiredMixin, View):
    admin_permissions_required = (CustomUser.ADMIN_PERMISSION_COMPANIES,)

    def post(self, request, pk):
        azienda = get_object_or_404(Azienda, pk=pk)
        stato_contratto = (request.POST.get('stato_contratto') or '').strip()
        legacy_value = request.POST.get('contratto_saldato')
        valid_statuses = {value for value, _label in Azienda.CONTRATTO_STATUS_CHOICES}

        if stato_contratto in valid_statuses:
            nuovo_stato = stato_contratto
        elif legacy_value in ('1', 'true', 'True', 'on'):
            nuovo_stato = Azienda.CONTRATTO_SALDATO
        elif legacy_value in ('0', 'false', 'False'):
            nuovo_stato = Azienda.CONTRATTO_NON_SALDATO
        else:
            messages.error(request, 'Seleziona uno stato contratto valido.')
            next_url = request.POST.get('next')
            if next_url:
                return redirect(next_url)
            return redirect('admin_azienda_detail', pk=pk)

        azienda.stato_contratto = nuovo_stato
        azienda.save(update_fields=['stato_contratto'])
        messages.success(request, f'Stato contratto aggiornato per {azienda.display_name}.')
        next_url = request.POST.get('next')
        if next_url:
            return redirect(next_url)
        return redirect('admin_azienda_detail', pk=pk)


class AdminAggiornaNotificheAziendaView(AdminPermissionRequiredMixin, View):
    admin_permissions_required = (CustomUser.ADMIN_PERMISSION_COMPANIES,)

    def post(self, request, pk):
        azienda = get_object_or_404(Azienda, pk=pk)
        form = AziendaNotificationCcForm(request.POST)
        if form.is_valid():
            azienda.email_notifiche_cc = form.cleaned_data['email_notifiche_cc']
            azienda.save(update_fields=['email_notifiche_cc'])
            messages.success(request, 'Email in cc aggiornate con successo.')
            return redirect('admin_azienda_detail', pk=pk)

        return render(
            request,
            'aziende/admin_azienda_detail.html',
            get_admin_azienda_detail_context(request, azienda, notification_cc_form=form),
        )


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
            send_new_company_created_notification(azienda, request=request)
            messages.success(
                request,
                f'{azienda.display_name} creata con successo.',
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


class AdminReplaceInitialCompanyDocumentView(AdminPermissionRequiredMixin, View):
    admin_permissions_required = (CustomUser.ADMIN_PERMISSION_COMPANY_DOCUMENTS,)

    def post(self, request, pk, field_name):
        azienda = get_object_or_404(Azienda, pk=pk)
        initial_fields = dict(Azienda.INITIAL_DOCUMENT_FIELDS)
        if field_name not in initial_fields:
            raise Http404('Documento aziendale non disponibile.')

        is_logo = field_name == 'logo_azienda'
        form = build_replace_file_form(
            request.POST,
            request.FILES,
            validator=validate_company_logo_upload if is_logo else validate_company_document_upload,
            file_help_text=(
                'Formati ammessi: PNG, JPG, JPEG, SVG, WEBP. Max '
                f'{COMPANY_LOGO_MAX_UPLOAD_SIZE // (1024 * 1024)} MB.'
                if is_logo else
                'Formati ammessi: PDF, DOCX. Max '
                f'{COMPANY_DOCUMENT_MAX_UPLOAD_SIZE // (1024 * 1024)} MB.'
            ),
            accept='.png,.jpg,.jpeg,.svg,.webp' if is_logo else '.pdf,.docx',
            include_note=field_name == 'varie_documento',
            note_initial=azienda.varie_note,
            note_label='Note documento',
        )
        if not form.is_valid():
            add_form_errors_message(request, form, 'Errore nella sostituzione del documento.')
            return redirect('admin_azienda_detail', pk=pk)

        if field_name == 'varie_documento':
            azienda.varie_note = form.cleaned_data.get('note', '')
        replace_model_file(
            azienda,
            field_name,
            form.cleaned_data['file'],
            extra_updates=['varie_note'] if field_name == 'varie_documento' else None,
        )
        messages.success(request, f'{initial_fields[field_name]} sostituito con successo.')
        return redirect('admin_azienda_detail', pk=pk)


class AdminReplaceCompanyDocumentView(AdminPermissionRequiredMixin, View):
    admin_permissions_required = (CustomUser.ADMIN_PERMISSION_COMPANY_DOCUMENTS,)

    def post(self, request, pk, documento_pk):
        azienda = get_object_or_404(Azienda, pk=pk)
        documento = get_object_or_404(DocumentoAziendale, pk=documento_pk, azienda=azienda)
        form = build_replace_file_form(
            request.POST,
            request.FILES,
            validator=validate_company_document_upload,
            file_help_text='Formati ammessi: PDF, DOCX. Max 10 MB.',
            accept='.pdf,.docx',
        )
        if not form.is_valid():
            add_form_errors_message(request, form, 'Errore nella sostituzione del documento.')
            return redirect('admin_azienda_detail', pk=pk)

        replace_model_file(documento, 'file', form.cleaned_data['file'])
        messages.success(request, f'Documento "{documento.titolo}" sostituito con successo.')
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
            'show_optional_account_notice': True,
            'back_href': reverse('admin_azienda_detail', args=[azienda.pk]),
            'back_label': 'Torna alla scheda azienda',
        })

    def post(self, request, pk):
        azienda = get_object_or_404(Azienda, pk=pk)
        form = LavoratoreForm(request.POST, azienda=azienda, include_account_fields=True)
        if form.is_valid():
            lavoratore = create_lavoratore_with_optional_account(form, azienda, request=request)
            messages.success(request, get_lavoratore_create_success_message(lavoratore))
            return redirect('admin_azienda_detail', pk=azienda.pk)
        return render(request, 'aziende/azienda_lavoratore_form.html', {
            'form': form,
            'azienda': azienda,
            'action': 'Nuovo lavoratore',
            'is_admin_context': True,
            'show_optional_account_notice': True,
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
        return render(
            request,
            'aziende/admin_lavoratore_detail.html',
            get_admin_lavoratore_detail_context(request, lavoratore),
        )


class AdminLavoratoreCreateAccountView(AdminPermissionRequiredMixin, View):
    admin_permissions_required = (
        CustomUser.ADMIN_PERMISSION_WORKERS,
        CustomUser.ADMIN_PERMISSION_COMPANIES,
    )
    admin_permissions_mode = 'any'

    def post(self, request, pk):
        lavoratore = get_object_or_404(Lavoratore, pk=pk)
        if lavoratore.user_id:
            messages.warning(request, 'Questo lavoratore ha già un account collegato.')
            return redirect('admin_lavoratore_detail', pk=pk)

        form = CreaAccountLavoratoreForm(request.POST, lavoratore=lavoratore)
        if form.is_valid():
            create_account_for_lavoratore(
                lavoratore,
                form.cleaned_data['account_email'],
                request=request,
            )
            messages.success(request, 'Account lavoratore creato e collegato con successo.')
            return redirect('admin_lavoratore_detail', pk=pk)

        return render(
            request,
            'aziende/admin_lavoratore_detail.html',
            get_admin_lavoratore_detail_context(request, lavoratore, account_form=form),
        )


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
                send_platform_email(subject, corpo, [lavoratore.user.email])
        else:
            messages.error(request, 'Errore nel caricamento del documento.')
        return redirect('admin_lavoratore_detail', pk=pk)


class AdminReplaceWorkerDocumentView(AdminPermissionRequiredMixin, View):
    admin_permissions_required = (CustomUser.ADMIN_PERMISSION_MEDICAL_RECORDS,)

    def post(self, request, pk, documento_pk):
        lavoratore = get_object_or_404(Lavoratore, pk=pk)
        cartella, _ = CartellaClinica.objects.get_or_create(lavoratore=lavoratore)
        documento = get_object_or_404(DocumentoSanitario, pk=documento_pk, cartella=cartella)
        form = build_replace_file_form(
            request.POST,
            request.FILES,
            validator=validate_document_upload,
            file_help_text='Formati ammessi: PDF, DOCX. Max 10 MB.',
            accept='.pdf,.docx',
        )
        if not form.is_valid():
            add_form_errors_message(request, form, 'Errore nella sostituzione del documento.')
            return redirect('admin_lavoratore_detail', pk=pk)

        replace_model_file(documento, 'file', form.cleaned_data['file'])
        messages.success(request, f'Documento "{documento.titolo}" sostituito con successo.')
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
            subject = 'Giudizio di idoneità disponibile su MedLavDelta'
            corpo = (
                "Gentile,\n"
                "Le comunichiamo che Centro Delta ha caricato sulla piattaforma MedLavDelta "
                f"il giudizio di idoneità alla mansione relativo al lavoratore {lavoratore.nome_completo}.\n"
                "Il documento è ora consultabile accedendo alla sua area riservata.\n"
                "https://medlavdelta.it/accounts/login/\n"
                "Per qualsiasi informazione, rimaniamo a sua disposizione.\n"
                "Cordiali saluti,\n"
                "Centro Delta"
            )
            send_company_notification_email(azienda, subject, corpo)
            messages.success(request, 'Esito idoneità registrato.')
        else:
            messages.error(request, "Errore nella registrazione dell'esito.")
        return redirect('admin_lavoratore_detail', pk=pk)


class AdminReplaceWorkerCertificateView(AdminPermissionRequiredMixin, View):
    admin_permissions_required = (CustomUser.ADMIN_PERMISSION_MEDICAL_RECORDS,)

    def post(self, request, pk, esito_pk):
        lavoratore = get_object_or_404(Lavoratore, pk=pk)
        esito = get_object_or_404(EsitoIdoneita, pk=esito_pk, lavoratore=lavoratore)
        form = build_replace_file_form(
            request.POST,
            request.FILES,
            validator=validate_document_upload,
            file_help_text='Formati ammessi: PDF, DOCX. Max 10 MB.',
            accept='.pdf,.docx',
        )
        if not form.is_valid():
            add_form_errors_message(request, form, 'Errore nella sostituzione del certificato.')
            return redirect('admin_lavoratore_detail', pk=pk)

        replace_model_file(esito, 'certificato', form.cleaned_data['file'])
        messages.success(request, 'Certificato sostituito con successo.')
        return redirect('admin_lavoratore_detail', pk=pk)


class AdminEditEsitoScadenzaView(AdminPermissionRequiredMixin, View):
    admin_permissions_required = (CustomUser.ADMIN_PERMISSION_MEDICAL_RECORDS,)

    def post(self, request, pk, esito_pk):
        lavoratore = get_object_or_404(Lavoratore, pk=pk)
        esito = get_object_or_404(EsitoIdoneita, pk=esito_pk, lavoratore=lavoratore)
        form = EsitoScadenzaForm(request.POST, instance=esito)
        if form.is_valid():
            form.save()
            messages.success(request, 'Data di scadenza aggiornata.')
        else:
            messages.error(request, 'Errore nella modifica della scadenza.')
        return redirect('admin_lavoratore_detail', pk=pk)


class AziendaDashboardView(AziendaRequiredMixin, View):
    def get(self, request):
        return render(
            request,
            'aziende/azienda_dashboard.html',
            get_azienda_dashboard_context(request, request.azienda),
        )


class AziendaGuideView(AziendaRequiredMixin, View):
    def get(self, request):
        if not COMPANY_GUIDE_PATH.exists():
            raise Http404('Guida aziende non disponibile.')

        response = FileResponse(
            COMPANY_GUIDE_PATH.open('rb'),
            content_type='application/pdf',
        )
        response['Content-Disposition'] = f'inline; filename="{COMPANY_GUIDE_FILENAME}"'
        return response


class AziendaDocumentiView(AziendaRequiredMixin, View):
    def get(self, request):
        context = {
            'azienda': request.azienda,
            'document_form': DocumentoAziendaleForm(),
            **get_azienda_documenti_context(request.azienda),
        }
        return render(request, 'aziende/azienda_documenti.html', context)


class AziendaCaricaDocumentoView(AziendaRequiredMixin, View):
    requires_company_write_access = True

    def post(self, request):
        form = DocumentoAziendaleForm(request.POST, request.FILES)
        if form.is_valid():
            documento = form.save(commit=False)
            documento.azienda = request.azienda
            documento.origine = DocumentoAziendale.ORIGINE_AZIENDA
            documento.caricato_da = request.user
            documento.save()
            messages.success(request, 'Documento caricato con successo.')
        else:
            messages.error(request, 'Errore nel caricamento del documento.')
        return redirect('azienda_documenti')


class AziendaLavoratoreCreateView(AziendaRequiredMixin, View):
    requires_company_write_access = True

    def get(self, request):
        form = LavoratoreForm(azienda=request.azienda, include_account_fields=True)
        return render(request, 'aziende/azienda_lavoratore_form.html', {
            'form': form,
            'azienda': request.azienda,
            'action': 'Nuovo lavoratore',
            'show_optional_account_notice': True,
            'back_href': reverse('azienda_dashboard'),
            'back_label': 'Torna alla lista',
        })

    def post(self, request):
        form = LavoratoreForm(request.POST, azienda=request.azienda, include_account_fields=True)
        if form.is_valid():
            lavoratore = create_lavoratore_with_optional_account(form, request.azienda, request=request)
            messages.success(request, get_lavoratore_create_success_message(lavoratore))
            return redirect('azienda_dashboard')
        return render(request, 'aziende/azienda_lavoratore_form.html', {
            'form': form,
            'azienda': request.azienda,
            'action': 'Nuovo lavoratore',
            'show_optional_account_notice': True,
            'back_href': reverse('azienda_dashboard'),
            'back_label': 'Torna alla lista',
        })


class AziendaLavoratoreEditView(AziendaRequiredMixin, View):
    requires_company_write_access = True

    def get(self, request, pk):
        lavoratore = get_object_or_404(Lavoratore, pk=pk, azienda=request.azienda)
        form = LavoratoreForm(instance=lavoratore, azienda=request.azienda)
        return render(request, 'aziende/azienda_lavoratore_form.html', {
            'form': form,
            'azienda': request.azienda,
            'action': 'Modifica lavoratore',
            'back_href': reverse('azienda_dashboard'),
            'back_label': 'Torna alla lista',
        })

    def post(self, request, pk):
        lavoratore = get_object_or_404(Lavoratore, pk=pk, azienda=request.azienda)
        form = LavoratoreForm(request.POST, instance=lavoratore, azienda=request.azienda)
        if form.is_valid():
            form.save()
            messages.success(request, 'Lavoratore aggiornato.')
            return redirect('azienda_dashboard')
        return render(request, 'aziende/azienda_lavoratore_form.html', {
            'form': form,
            'azienda': request.azienda,
            'action': 'Modifica lavoratore',
            'back_href': reverse('azienda_dashboard'),
            'back_label': 'Torna alla lista',
        })


class AziendaLavoratoreDetailView(AziendaRequiredMixin, View):
    def get(self, request, pk):
        lavoratore = get_object_or_404(Lavoratore, pk=pk, azienda=request.azienda)
        return render(
            request,
            'aziende/azienda_lavoratore.html',
            get_azienda_lavoratore_detail_context(lavoratore),
        )


class AziendaLavoratoreCreateAccountView(AziendaRequiredMixin, View):
    requires_company_write_access = True

    def post(self, request, pk):
        lavoratore = get_object_or_404(Lavoratore, pk=pk, azienda=request.azienda)
        if lavoratore.user_id:
            messages.warning(request, 'Questo lavoratore ha già un account collegato.')
            return redirect('azienda_lavoratore', pk=pk)

        form = CreaAccountLavoratoreForm(request.POST, lavoratore=lavoratore)
        if form.is_valid():
            create_account_for_lavoratore(
                lavoratore,
                form.cleaned_data['account_email'],
                request=request,
            )
            messages.success(request, 'Account lavoratore creato e collegato con successo.')
            return redirect('azienda_lavoratore', pk=pk)

        return render(
            request,
            'aziende/azienda_lavoratore.html',
            get_azienda_lavoratore_detail_context(lavoratore, account_form=form),
        )


class AziendaReplaceWorkerCertificateView(AziendaRequiredMixin, View):
    requires_company_write_access = True

    def post(self, request, pk, esito_pk):
        lavoratore = get_object_or_404(Lavoratore, pk=pk, azienda=request.azienda)
        esito = get_object_or_404(EsitoIdoneita, pk=esito_pk, lavoratore=lavoratore)
        form = build_replace_file_form(
            request.POST,
            request.FILES,
            validator=validate_document_upload,
            file_help_text='Formati ammessi: PDF, DOCX. Max 10 MB.',
            accept='.pdf,.docx',
        )
        if not form.is_valid():
            add_form_errors_message(request, form, 'Errore nella sostituzione del certificato.')
            return redirect('azienda_lavoratore', pk=pk)

        replace_model_file(esito, 'certificato', form.cleaned_data['file'])
        messages.success(request, 'Certificato sostituito con successo.')
        return redirect('azienda_lavoratore', pk=pk)


class AziendaReadOnlyAccountCreateView(AziendaRequiredMixin, View):
    requires_company_write_access = True

    def post(self, request):
        form = CreaAccountAziendaReadOnlyForm(request.POST, azienda=request.azienda)
        if form.is_valid():
            create_read_only_account_for_azienda(
                request.azienda,
                form.cleaned_data['account_email'],
                request=request,
            )
            messages.success(request, 'Account azienda in sola lettura creato con successo.')
            return redirect('azienda_dashboard')

        return render(
            request,
            'aziende/azienda_dashboard.html',
            get_azienda_dashboard_context(request, request.azienda, read_only_account_form=form),
        )


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
