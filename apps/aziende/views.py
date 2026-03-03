from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from apps.accounts.mixins import AdminRequiredMixin, AziendaRequiredMixin
from .models import Azienda, Lavoratore, Sede
from apps.sanitaria.models import EsitoIdoneita


# ─── ADMIN ────────────────────────────────────────────────

class AdminDashboardView(AdminRequiredMixin, View):
    def get(self, request):
        context = {
            'aziende': Azienda.objects.all().order_by('ragione_sociale'),
            'totale_aziende': Azienda.objects.count(),
            'totale_lavoratori': Lavoratore.objects.filter(attivo=True).count(),
        }
        return render(request, 'aziende/admin_dashboard.html', context)


class AdminLavoratoriView(AdminRequiredMixin, View):
    def get(self, request):
        lavoratori = Lavoratore.objects.select_related(
            'azienda', 'sede'
        ).filter(attivo=True).order_by('azienda', 'cognome')
        return render(request, 'aziende/admin_lavoratori.html', {
            'lavoratori': lavoratori
        })


# ─── AZIENDA ──────────────────────────────────────────────

class AziendaDashboardView(AziendaRequiredMixin, View):
    def get(self, request):
        azienda = get_object_or_404(Azienda, user=request.user)
        lavoratori = Lavoratore.objects.filter(
            azienda=azienda, attivo=True
        ).order_by('cognome')

        # Idoneità recenti comunicati all'azienda
        esiti = EsitoIdoneita.objects.filter(
            lavoratore__azienda=azienda
        ).order_by('-data_visita')[:10]

        context = {
            'azienda': azienda,
            'lavoratori': lavoratori,
            'esiti': esiti,
            'totale_lavoratori': lavoratori.count(),
        }
        return render(request, 'aziende/azienda_dashboard.html', context)


class AziendaLavoratoreDetailView(AziendaRequiredMixin, View):
    def get(self, request, pk):
        azienda = get_object_or_404(Azienda, user=request.user)
        lavoratore = get_object_or_404(
            Lavoratore, pk=pk, azienda=azienda
        )
        # Solo l'esito idoneità — nessun dato clinico
        esiti = EsitoIdoneita.objects.filter(
            lavoratore=lavoratore
        ).order_by('-data_visita')
        return render(request, 'aziende/azienda_lavoratore.html', {
            'lavoratore': lavoratore,
            'esiti': esiti,
        })


# ─── OPERATORE ────────────────────────────────────────────

class OperatoreDashboardView(View):
    def dispatch(self, request, *args, **kwargs):
        from django.contrib.auth.mixins import LoginRequiredMixin
        if not request.user.is_authenticated or not request.user.is_operatore:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        lavoratore = get_object_or_404(Lavoratore, user=request.user)
        cartella = getattr(lavoratore, 'cartella', None)
        esiti = EsitoIdoneita.objects.filter(
            lavoratore=lavoratore
        ).order_by('-data_visita')
        documenti = cartella.documenti.order_by('-data') if cartella else []
        return render(request, 'aziende/operatore_dashboard.html', {
            'lavoratore': lavoratore,
            'cartella': cartella,
            'esiti': esiti,
            'documenti': documenti,
        })