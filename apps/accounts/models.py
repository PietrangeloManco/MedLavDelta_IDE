# Create your models here.
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email obbligatoria')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'admin')
        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractBaseUser, PermissionsMixin):
    ADMIN = 'admin'
    AZIENDA = 'azienda'
    OPERATORE = 'operatore'

    ADMIN_PERMISSION_DASHBOARD = 'dashboard_access'
    ADMIN_PERMISSION_COMPANIES = 'company_profiles_manage'
    ADMIN_PERMISSION_COMPANY_DOCUMENTS = 'company_documents_manage'
    ADMIN_PERMISSION_WORKERS = 'workers_manage'
    ADMIN_PERMISSION_MEDICAL_RECORDS = 'medical_records_manage'
    ADMIN_PERMISSION_PREVENTIVI = 'preventives_manage'
    ADMIN_PERMISSION_FATTURE = 'invoices_manage'

    ROLE_CHOICES = [
        (ADMIN, 'Amministratore'),
        (AZIENDA, 'Azienda / Datore di lavoro'),
        (OPERATORE, 'Operatore / Lavoratore'),
    ]

    ADMIN_PERMISSION_CHOICES = [
        (ADMIN_PERMISSION_DASHBOARD, 'Accesso al pannello di controllo e alle scadenze'),
        (ADMIN_PERMISSION_COMPANIES, 'Gestione profili aziendali e stato contratti'),
        (ADMIN_PERMISSION_COMPANY_DOCUMENTS, 'Consultazione e caricamento documenti aziendali'),
        (ADMIN_PERMISSION_WORKERS, 'Consultazione elenco lavoratori'),
        (ADMIN_PERMISSION_MEDICAL_RECORDS, 'Cartelle sanitarie, documenti medici ed esiti'),
        (ADMIN_PERMISSION_PREVENTIVI, 'Gestione preventivi'),
        (ADMIN_PERMISSION_FATTURE, 'Gestione fatture'),
    ]

    email = models.EmailField(unique=True, verbose_name='Email')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, verbose_name='Ruolo')
    admin_permissions = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Permessi admin limitato',
        help_text='Elenco provvisorio dei permessi assegnati agli admin non superuser.',
    )
    is_active = models.BooleanField(default=True, verbose_name='Attivo')
    is_staff = models.BooleanField(default=False, verbose_name='Accesso amministrazione')
    data_creazione = models.DateTimeField(auto_now_add=True, verbose_name='Data creazione')

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    objects = CustomUserManager()

    class Meta:
        verbose_name = 'Utente'
        verbose_name_plural = 'Utenti'

    def __str__(self):
        return f'{self.email} ({self.get_role_display()})'

    @property
    def is_admin(self):
        return self.role == self.ADMIN

    @property
    def is_azienda(self):
        return self.role == self.AZIENDA

    @property
    def is_operatore(self):
        return self.role == self.OPERATORE

    def has_admin_permission(self, permission_code):
        if not self.is_admin:
            return False
        if self.is_superuser:
            return True
        return permission_code in (self.admin_permissions or [])

    @property
    def admin_permission_map(self):
        permissions = {
            code: self.has_admin_permission(code)
            for code, _label in self.ADMIN_PERMISSION_CHOICES
        }
        permissions['full_access'] = self.is_superuser
        permissions['has_limited_permissions'] = bool(self.admin_permissions)
        return permissions
