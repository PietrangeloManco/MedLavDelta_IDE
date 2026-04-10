from django.contrib import messages
from django.db.models import CharField, DecimalField, ExpressionWrapper, F, Sum, Value
from django.db.models.functions import Cast, Coalesce, Concat
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.accounts.listing import apply_sorting, apply_text_search, get_list_search_term
from apps.accounts.mixins import AdminPermissionRequiredMixin
from apps.accounts.models import CustomUser
from apps.aziende.models import Azienda

from .documents import (
    build_invoice_pdf_bytes,
    build_quote_pdf_bytes,
    build_invoice_xml_bytes,
    invoice_pdf_filename,
    invoice_xml_filename,
    preventivo_pdf_filename,
)
from .forms import (
    FatturaForm,
    FatturaVoceFormSet,
    PreventivoForm,
    PreventivoVoceFormSet,
)
from .models import Fattura, Preventivo


DOCUMENT_TOTAL_ZERO = Value(0, output_field=DecimalField(max_digits=12, decimal_places=2))


def with_document_total_annotations(queryset):
    line_total = ExpressionWrapper(
        F('voci__quantita') * F('voci__costo_unitario') * (
            Value(1, output_field=DecimalField(max_digits=12, decimal_places=2))
            - F('voci__sconto_percentuale') / Value(100, output_field=DecimalField(max_digits=12, decimal_places=2))
        ),
        output_field=DecimalField(max_digits=12, decimal_places=2),
    )
    return queryset.annotate(
        totale_imponibile_ordinamento=Coalesce(
            Sum(line_total),
            DOCUMENT_TOTAL_ZERO,
        )
    ).annotate(
        totale_complessivo_ordinamento=ExpressionWrapper(
            F('totale_imponibile_ordinamento') * (
                Value(1, output_field=DecimalField(max_digits=12, decimal_places=2))
                + F('aliquota_iva') / Value(100, output_field=DecimalField(max_digits=12, decimal_places=2))
            ),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
    )


class AdminPreventiviListView(AdminPermissionRequiredMixin, View):
    admin_permissions_required = (CustomUser.ADMIN_PERMISSION_PREVENTIVI,)

    def get(self, request):
        preventivi = with_document_total_annotations(
            Preventivo.objects.select_related('azienda').prefetch_related('voci').annotate(
                numero_preventivo_text=Cast('numero_preventivo', CharField()),
            )
        )
        azienda_pk = request.GET.get('azienda')
        azienda_selezionata = None
        if azienda_pk:
            azienda_selezionata = get_object_or_404(Azienda, pk=azienda_pk)
            preventivi = preventivi.filter(azienda=azienda_selezionata)
        current_search = get_list_search_term(request)
        preventivi = apply_text_search(
            preventivi,
            current_search,
            (
                'numero_preventivo_text',
                'azienda__ragione_sociale',
                'oggetto',
                'descrizione_oggetto',
            ),
        )
        preventivi, current_sort, current_dir = apply_sorting(
            preventivi,
            sort_key=request.GET.get('sort'),
            direction=request.GET.get('dir'),
            sort_map={
                'numero': ('numero_preventivo',),
                'data': ('data_preventivo', 'numero_preventivo'),
                'cliente': ('azienda__ragione_sociale', 'numero_preventivo'),
                'oggetto': ('oggetto', 'numero_preventivo'),
                'imponibile': ('totale_imponibile_ordinamento', 'numero_preventivo'),
                'totale': ('totale_complessivo_ordinamento', 'numero_preventivo'),
            },
            default_sort='data',
            default_dir='desc',
        )
        context = {
            'preventivi': preventivi,
            'aziende': Azienda.objects.order_by('ragione_sociale'),
            'azienda_selezionata': azienda_selezionata,
            'current_search': current_search,
            'current_sort': current_sort,
            'current_dir': current_dir,
        }
        return render(request, 'commerciale/admin_preventivi_list.html', context)


class AdminPreventivoCreateView(AdminPermissionRequiredMixin, View):
    admin_permissions_required = (CustomUser.ADMIN_PERMISSION_PREVENTIVI,)

    def get(self, request):
        form = PreventivoForm(initial=self._initial(request))
        formset = PreventivoVoceFormSet(prefix='voci')
        return render(request, 'commerciale/admin_preventivo_form.html', self._context(form, formset))

    def post(self, request):
        form = PreventivoForm(request.POST, initial=self._initial(request))
        formset = PreventivoVoceFormSet(request.POST, prefix='voci')
        if form.is_valid() and formset.is_valid():
            preventivo = form.save()
            formset.instance = preventivo
            formset.save()
            messages.success(request, f'Preventivo {preventivo.numero_formattato} salvato.')
            return redirect('admin_preventivi')
        return render(request, 'commerciale/admin_preventivo_form.html', self._context(form, formset))

    def _initial(self, request):
        azienda_pk = request.GET.get('azienda')
        if azienda_pk and Azienda.objects.filter(pk=azienda_pk).exists():
            return {'azienda': azienda_pk}
        return {}

    def _context(self, form, formset):
        return {
            'form': form,
            'formset': formset,
            'action': 'Nuovo preventivo',
            'submit_label': 'Salva preventivo',
        }


class AdminPreventivoUpdateView(AdminPermissionRequiredMixin, View):
    admin_permissions_required = (CustomUser.ADMIN_PERMISSION_PREVENTIVI,)

    def get(self, request, pk):
        preventivo = get_object_or_404(Preventivo, pk=pk)
        form = PreventivoForm(instance=preventivo)
        formset = PreventivoVoceFormSet(instance=preventivo, prefix='voci')
        return render(request, 'commerciale/admin_preventivo_form.html', self._context(form, formset, preventivo))

    def post(self, request, pk):
        preventivo = get_object_or_404(Preventivo, pk=pk)
        form = PreventivoForm(request.POST, instance=preventivo)
        formset = PreventivoVoceFormSet(request.POST, instance=preventivo, prefix='voci')
        if form.is_valid() and formset.is_valid():
            preventivo = form.save()
            formset.instance = preventivo
            formset.save()
            messages.success(request, f'Preventivo {preventivo.numero_formattato} aggiornato.')
            return redirect('admin_preventivi')
        return render(request, 'commerciale/admin_preventivo_form.html', self._context(form, formset, preventivo))

    def _context(self, form, formset, preventivo):
        return {
            'form': form,
            'formset': formset,
            'preventivo': preventivo,
            'action': f'Modifica preventivo {preventivo.numero_formattato}',
            'submit_label': 'Aggiorna preventivo',
        }


class AdminPreventivoPdfView(AdminPermissionRequiredMixin, View):
    admin_permissions_required = (CustomUser.ADMIN_PERMISSION_PREVENTIVI,)

    def get(self, request, pk):
        preventivo = get_object_or_404(Preventivo.objects.select_related('azienda').prefetch_related('voci'), pk=pk)
        response = HttpResponse(build_quote_pdf_bytes(preventivo), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{preventivo_pdf_filename(preventivo)}"'
        return response


class AdminFattureListView(AdminPermissionRequiredMixin, View):
    admin_permissions_required = (CustomUser.ADMIN_PERMISSION_FATTURE,)

    def get(self, request):
        fatture = with_document_total_annotations(
            Fattura.objects.select_related('azienda').prefetch_related('voci').annotate(
                numero_progressivo_text=Cast('numero_progressivo', CharField()),
                anno_fattura_text=Cast('anno_fattura', CharField()),
                numero_documento_search=Concat(
                    'prefisso_numero',
                    Value(' '),
                    Cast('numero_progressivo', CharField()),
                    output_field=CharField(),
                ),
                numero_completo_search=Concat(
                    'prefisso_numero',
                    Value('/'),
                    Cast('numero_progressivo', CharField()),
                    Value('/'),
                    Cast('anno_fattura', CharField()),
                    output_field=CharField(),
                ),
            )
        )
        azienda_pk = request.GET.get('azienda')
        azienda_selezionata = None
        if azienda_pk:
            azienda_selezionata = get_object_or_404(Azienda, pk=azienda_pk)
            fatture = fatture.filter(azienda=azienda_selezionata)
        current_search = get_list_search_term(request)
        fatture = apply_text_search(
            fatture,
            current_search,
            (
                'numero_documento_search',
                'numero_completo_search',
                'azienda__ragione_sociale',
                'categoria_merceologica',
                'modalita_pagamento',
                'note',
            ),
        )
        fatture, current_sort, current_dir = apply_sorting(
            fatture,
            sort_key=request.GET.get('sort'),
            direction=request.GET.get('dir'),
            sort_map={
                'numero': ('anno_fattura', 'numero_progressivo'),
                'data': ('data_fattura', 'numero_progressivo'),
                'scadenza': ('scadenza', 'numero_progressivo'),
                'categoria': ('categoria_merceologica', 'numero_progressivo'),
                'intestatario': ('azienda__ragione_sociale', 'numero_progressivo'),
                'pagamento': ('modalita_pagamento', 'numero_progressivo'),
                'imponibile': ('totale_imponibile_ordinamento', 'numero_progressivo'),
                'totale': ('totale_complessivo_ordinamento', 'numero_progressivo'),
                'inviata': ('inviata_il', 'numero_progressivo'),
                'incassata': ('data_incasso', 'numero_progressivo'),
            },
            default_sort='data',
            default_dir='desc',
        )
        context = {
            'fatture': fatture,
            'aziende': Azienda.objects.order_by('ragione_sociale'),
            'azienda_selezionata': azienda_selezionata,
            'current_search': current_search,
            'current_sort': current_sort,
            'current_dir': current_dir,
        }
        return render(request, 'commerciale/admin_fatture_list.html', context)


class AdminFatturaCreateView(AdminPermissionRequiredMixin, View):
    admin_permissions_required = (CustomUser.ADMIN_PERMISSION_FATTURE,)

    def get(self, request):
        form = FatturaForm(initial=self._initial(request))
        formset = FatturaVoceFormSet(prefix='voci')
        return render(request, 'commerciale/admin_fattura_form.html', self._context(form, formset))

    def post(self, request):
        form = FatturaForm(request.POST, initial=self._initial(request))
        formset = FatturaVoceFormSet(request.POST, prefix='voci')
        if form.is_valid() and formset.is_valid():
            fattura = form.save()
            formset.instance = fattura
            formset.save()
            messages.success(request, f'Fattura {fattura.numero_completo} salvata.')
            return redirect('admin_fatture')
        return render(request, 'commerciale/admin_fattura_form.html', self._context(form, formset))

    def _initial(self, request):
        azienda_pk = request.GET.get('azienda')
        if azienda_pk and Azienda.objects.filter(pk=azienda_pk).exists():
            return {'azienda': azienda_pk}
        return {}

    def _context(self, form, formset):
        return {
            'form': form,
            'formset': formset,
            'action': 'Nuova fattura',
            'submit_label': 'Salva fattura',
        }


class AdminFatturaUpdateView(AdminPermissionRequiredMixin, View):
    admin_permissions_required = (CustomUser.ADMIN_PERMISSION_FATTURE,)

    def get(self, request, pk):
        fattura = get_object_or_404(Fattura, pk=pk)
        form = FatturaForm(instance=fattura)
        formset = FatturaVoceFormSet(instance=fattura, prefix='voci')
        return render(request, 'commerciale/admin_fattura_form.html', self._context(form, formset, fattura))

    def post(self, request, pk):
        fattura = get_object_or_404(Fattura, pk=pk)
        form = FatturaForm(request.POST, instance=fattura)
        formset = FatturaVoceFormSet(request.POST, instance=fattura, prefix='voci')
        if form.is_valid() and formset.is_valid():
            fattura = form.save()
            formset.instance = fattura
            formset.save()
            messages.success(request, f'Fattura {fattura.numero_completo} aggiornata.')
            return redirect('admin_fatture')
        return render(request, 'commerciale/admin_fattura_form.html', self._context(form, formset, fattura))

    def _context(self, form, formset, fattura):
        return {
            'form': form,
            'formset': formset,
            'fattura': fattura,
            'action': f'Modifica fattura {fattura.numero_documento}',
            'submit_label': 'Aggiorna fattura',
        }


class AdminFatturaPdfView(AdminPermissionRequiredMixin, View):
    admin_permissions_required = (CustomUser.ADMIN_PERMISSION_FATTURE,)

    def get(self, request, pk):
        fattura = get_object_or_404(Fattura.objects.select_related('azienda').prefetch_related('voci'), pk=pk)
        response = HttpResponse(build_invoice_pdf_bytes(fattura), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{invoice_pdf_filename(fattura)}"'
        return response


class AdminFatturaXmlView(AdminPermissionRequiredMixin, View):
    admin_permissions_required = (CustomUser.ADMIN_PERMISSION_FATTURE,)

    def get(self, request, pk):
        fattura = get_object_or_404(Fattura.objects.select_related('azienda').prefetch_related('voci'), pk=pk)
        response = HttpResponse(build_invoice_xml_bytes(fattura), content_type='application/xml')
        response['Content-Disposition'] = f'attachment; filename="{invoice_xml_filename(fattura)}"'
        return response


class AdminAziendaCondizioniPagamentoApiView(AdminPermissionRequiredMixin, View):
    admin_permissions_required = (
        CustomUser.ADMIN_PERMISSION_PREVENTIVI,
        CustomUser.ADMIN_PERMISSION_FATTURE,
    )
    admin_permissions_mode = 'any'

    def get(self, request, pk):
        azienda = get_object_or_404(Azienda, pk=pk)
        sede = azienda.sedi.order_by('id').first()
        return JsonResponse({
            'condizioni_pagamento_riservate': azienda.condizioni_pagamento_riservate,
            'indirizzo_fatturazione': sede.indirizzo if sede else '',
            'cap_fatturazione': sede.cap if sede else '',
            'comune_fatturazione': sede.citta if sede else '',
            'provincia_fatturazione': sede.provincia if sede else '',
        })
