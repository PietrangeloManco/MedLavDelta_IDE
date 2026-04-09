from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import render

from apps.aziende.models import Azienda


class AdminPermissionRequiredMixin(LoginRequiredMixin):
    admin_permissions_required = ()
    admin_permissions_mode = 'all'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_admin:
            raise PermissionDenied

        required_permissions = tuple(self.admin_permissions_required or ())
        if request.user.is_superuser or not required_permissions:
            return super().dispatch(request, *args, **kwargs)

        checks = [
            request.user.has_admin_permission(permission_code)
            for permission_code in required_permissions
        ]
        has_access = all(checks) if self.admin_permissions_mode == 'all' else any(checks)
        if not has_access:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class AziendaRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_azienda:
            raise PermissionDenied
        azienda = Azienda.objects.filter(user=request.user).first()
        if not azienda:
            raise PermissionDenied
        request.azienda = azienda
        if not azienda.contratto_saldato:
            return render(request, 'aziende/azienda_contratto_non_saldato.html', {
                'azienda': azienda,
            })
        return super().dispatch(request, *args, **kwargs)


class OperatoreRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_operatore:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)
