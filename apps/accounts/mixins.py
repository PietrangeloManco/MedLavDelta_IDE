from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied


class AdminRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_admin:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class AziendaRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_azienda:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class OperatoreRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_operatore:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)