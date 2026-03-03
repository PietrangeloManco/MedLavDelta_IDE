from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import render, redirect
from django.views import View
from django.contrib.auth.decorators import login_required


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
        return redirect('admin_dashboard')
    elif user.is_azienda:
        return redirect('azienda_dashboard')
    elif user.is_operatore:
        return redirect('operatore_dashboard')
    return redirect('login')