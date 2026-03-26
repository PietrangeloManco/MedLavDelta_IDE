from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.accounts.mixins import AdminPermissionRequiredMixin
from apps.accounts.models import CustomUser
from apps.aziende.models import Azienda

from .forms import (
    FatturaForm,
    FatturaVoceFormSet,
    PreventivoForm,
    PreventivoVoceFormSet,
)
from .models import Fattura, Preventivo


class AdminPreventiviListView(AdminPermissionRequiredMixin, View):
    admin_permissions_required = (CustomUser.ADMIN_PERMISSION_PREVENTIVI,)

    def get(self, request):
        preventivi = Preventivo.objects.select_related('azienda').prefetch_related('voci')
        azienda_pk = request.GET.get('azienda')
        azienda_selezionata = None
        if azienda_pk:
            azienda_selezionata = get_object_or_404(Azienda, pk=azienda_pk)
            preventivi = preventivi.filter(azienda=azienda_selezionata)
        context = {
            'preventivi': preventivi,
            'aziende': Azienda.objects.order_by('ragione_sociale'),
            'azienda_selezionata': azienda_selezionata,
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


class AdminFattureListView(AdminPermissionRequiredMixin, View):
    admin_permissions_required = (CustomUser.ADMIN_PERMISSION_FATTURE,)

    def get(self, request):
        fatture = Fattura.objects.select_related('azienda').prefetch_related('voci')
        azienda_pk = request.GET.get('azienda')
        azienda_selezionata = None
        if azienda_pk:
            azienda_selezionata = get_object_or_404(Azienda, pk=azienda_pk)
            fatture = fatture.filter(azienda=azienda_selezionata)
        context = {
            'fatture': fatture,
            'aziende': Azienda.objects.order_by('ragione_sociale'),
            'azienda_selezionata': azienda_selezionata,
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
            'action': f'Modifica fattura {fattura.numero_completo}',
            'submit_label': 'Aggiorna fattura',
        }


class AdminAziendaCondizioniPagamentoApiView(AdminPermissionRequiredMixin, View):
    admin_permissions_required = (
        CustomUser.ADMIN_PERMISSION_PREVENTIVI,
        CustomUser.ADMIN_PERMISSION_FATTURE,
    )
    admin_permissions_mode = 'any'

    def get(self, request, pk):
        azienda = get_object_or_404(Azienda, pk=pk)
        return JsonResponse({
            'condizioni_pagamento_riservate': azienda.condizioni_pagamento_riservate,
        })
