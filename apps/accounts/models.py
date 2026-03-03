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

    ROLE_CHOICES = [
        (ADMIN, 'Amministratore'),
        (AZIENDA, 'Azienda / Datore di lavoro'),
        (OPERATORE, 'Operatore / Lavoratore'),
    ]

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    data_creazione = models.DateTimeField(auto_now_add=True)

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