from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views import View

from .models import CustomUser


class LoginView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('dashboard')
        form = AuthenticationForm()
        return render(request, 'accounts/login.html', {'form': form})

    def post(self, request):
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            return redirect('dashboard')
        return render(request, 'accounts/login.html', {'form': form})


class LogoutView(View):
    def post(self, request):
        logout(request)
        return redirect('login')


@login_required
def dashboard_router(request):
    user = request.user
    if user.is_admin:
        if user.has_admin_permission(CustomUser.ADMIN_PERMISSION_DASHBOARD):
            return redirect('admin_dashboard')
        if (
            user.has_admin_permission(CustomUser.ADMIN_PERMISSION_COMPANIES)
            or user.has_admin_permission(CustomUser.ADMIN_PERMISSION_COMPANY_DOCUMENTS)
            or user.has_admin_permission(CustomUser.ADMIN_PERMISSION_PREVENTIVI)
            or user.has_admin_permission(CustomUser.ADMIN_PERMISSION_FATTURE)
        ):
            return redirect('admin_aziende')
        if (
            user.has_admin_permission(CustomUser.ADMIN_PERMISSION_WORKERS)
            or user.has_admin_permission(CustomUser.ADMIN_PERMISSION_MEDICAL_RECORDS)
        ):
            return redirect('admin_lavoratori')
        if user.has_admin_permission(CustomUser.ADMIN_PERMISSION_PREVENTIVI):
            return redirect('admin_preventivi')
        if user.has_admin_permission(CustomUser.ADMIN_PERMISSION_FATTURE):
            return redirect('admin_fatture')
        return redirect('login')
    if user.is_azienda:
        return redirect('azienda_dashboard')
    if user.is_operatore:
        return redirect('operatore_dashboard')
    return redirect('login')
