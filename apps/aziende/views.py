from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from apps.accounts.mixins import AdminRequiredMixin, AziendaRequiredMixin, OperatoreRequiredMixin
from apps.accounts.models import CustomUser
from .models import Azienda, Lavoratore, Sede
from .forms import CreaAziendaForm, LavoratoreForm, CreaAccountOperatoreForm
from apps.sanitaria.models import EsitoIdoneita, CartellaClinica, DocumentoSanitario
from apps.sanitaria.forms import DocumentoSanitarioForm, EsitoIdoneitaForm
from datetime import timedelta
from django.utils import timezone

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
        form = CreaAziendaForm(request.POST)
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
                codice_fiscale=form.cleaned_data['codice_fiscale'],
                partita_iva=form.cleaned_data['partita_iva'],
                email_contatto=form.cleaned_data['email_contatto'],
                telefono=form.cleaned_data['telefono'],
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
        else:
            messages.error(request, 'Errore nel caricamento del documento.')
        return redirect('admin_lavoratore_detail', pk=pk)


class AdminRegistraEsitoView(AdminRequiredMixin, View):
    def post(self, request, pk):
        lavoratore = get_object_or_404(Lavoratore, pk=pk)
        form = EsitoIdoneitaForm(request.POST)
        if form.is_valid():
            esito = form.save(commit=False)
            esito.lavoratore = lavoratore
            esito.save()
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
        }
        return render(request, 'aziende/azienda_dashboard.html', context)


class AziendaLavoratoreCreateView(AziendaRequiredMixin, View):
    def get(self, request):
        azienda = getattr(request, 'azienda', None) or get_object_or_404(Azienda, user=request.user)
        form = LavoratoreForm(azienda=azienda)
        return render(request, 'aziende/azienda_lavoratore_form.html', {
            'form': form, 'azienda': azienda, 'action': 'Nuovo lavoratore'
        })

    def post(self, request):
        azienda = getattr(request, 'azienda', None) or get_object_or_404(Azienda, user=request.user)
        form = LavoratoreForm(request.POST, azienda=azienda)
        if form.is_valid():
            lavoratore = form.save(commit=False)
            lavoratore.azienda = azienda
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
    
class AdminCreaAccountOperatoreView(AdminRequiredMixin, View):
    def post(self, request, pk):
        lavoratore = get_object_or_404(Lavoratore, pk=pk)

        # Blocca se ha già un account
        if lavoratore.user:
            messages.warning(request, 'Questo lavoratore ha già un account.')
            return redirect('admin_lavoratore_detail', pk=pk)

        form = CreaAccountOperatoreForm(request.POST)
        if form.is_valid():
            user = CustomUser.objects.create_user(
                email=form.cleaned_data['email'],
                password=form.cleaned_data['password'],
                role=CustomUser.OPERATORE
            )
            lavoratore.user = user
            lavoratore.save()
            messages.success(request, f'Account creato per {lavoratore.nome_completo}.')
        else:
            messages.error(request, 'Errore nella creazione dell\'account.')

        return redirect('admin_lavoratore_detail', pk=pk)
