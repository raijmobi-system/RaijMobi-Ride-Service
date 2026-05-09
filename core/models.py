import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from .manager import SoftDeleteManager
from django.core.exceptions import ValidationError
from django.utils import timezone


# ==========================================
# 1. FUNÇÃO SENTINELA
# ==========================================
def get_sentinel_user_client():
    from core.models import UserClient

    sentinel_id = uuid.UUID(int=0)

    client, _ = UserClient.objects.get_or_create(
        id=sentinel_id,
        defaults={'nome': 'Deleted User Client'}
    )

    return client


# ==========================================
# 2. MIXINS ATÔMICOS
# ==========================================
class CreatedAtMixin(models.Model):
    created_at = models.DateTimeField(
        _("Created at"),
        auto_now_add=True,
        editable=False
    )

    class Meta:
        abstract = True


class UpdatedAtMixin(models.Model):
    updated_at = models.DateTimeField(
        _("Updated at"),
        auto_now=True
    )

    class Meta:
        abstract = True


class CreatedByMixin(models.Model):
    created_by = models.ForeignKey(
        'core.UserClient',
        verbose_name=_("Created by"),
        on_delete=models.SET(get_sentinel_user_client),
        null=True,
        related_name="created_%(app_label)s_%(class)s_set",
    )

    class Meta:
        abstract = True


class UpdatedByMixin(models.Model):
    updated_by = models.ForeignKey(
        'core.UserClient',
        verbose_name=_("Updated by"),
        on_delete=models.SET(get_sentinel_user_client),
        null=True,
        related_name="updated_%(app_label)s_%(class)s_set",
    )

    class Meta:
        abstract = True


# ==========================================
# 3. MIXINS AGRUPADOS
# ==========================================
class TimeStampedModel(CreatedAtMixin, UpdatedAtMixin):

    class Meta:
        abstract = True


class UserTrackedModel(CreatedByMixin, UpdatedByMixin):

    class Meta:
        abstract = True


# ==========================================
# 4. BASES GENÉRICAS
# ==========================================
class UUIDModel(models.Model):
    uuid = models.UUIDField(
        unique=True,
        editable=False,
        default=uuid.uuid4
    )

    class Meta:
        abstract = True


class SoftDeleteModel(models.Model):
    is_deleted = models.BooleanField(default=False)

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    def delete(self, *args, **kwargs):
        self.is_deleted = True
        self.save()

    class Meta:
        abstract = True


# ==========================================
# 5. MODELO USUÁRIO
# ==========================================
class UserClient(TimeStampedModel):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    nome = models.CharField(max_length=255)

    def __str__(self):
        return self.nome


# ==========================================
# 6. MODELOS BASE
# ==========================================
class BaseModel(UUIDModel, TimeStampedModel, UserTrackedModel):

    class Meta:
        abstract = True


class BaseModelWithSoftDelete(BaseModel, SoftDeleteModel):

    class Meta:
        abstract = True


# ==========================================
# VEHICLE
# ==========================================
class Vehicle(BaseModelWithSoftDelete):

    CORES_CHOICES = (
        ('vermelho', 'Vermelho'),
        ('laranja', 'Laranja'),
        ('amarelo', 'Amarelo'),
        ('verde', 'Verde'),
        ('azul', 'Azul'),
        ('anil', 'Anil'),
        ('violeta', 'Violeta'),
        ('rosa', 'Rosa'),
        ('preto', 'Preto'),
        ('branco', 'Branco'),
        ('cinza', 'Cinza'),
        ('prata', 'Prata'),
        ('marrom', 'Marrom'),
        ('bege', 'Bege'),
    )

    user = models.ForeignKey(
        UserClient,
        on_delete=models.CASCADE,
        related_name="veiculos"
    )

    model = models.CharField(max_length=100)

    color = models.CharField(
        max_length=50,
        choices=CORES_CHOICES
    )

    plate = models.CharField(max_length=10)

    seats = models.IntegerField()

    def __str__(self):
        return f"{self.model} - {self.plate}"


# ==========================================
# RIDE
# ==========================================
class Ride(BaseModelWithSoftDelete):

    STATUS_CHOICES = (
        ('pendente', 'Pendente'),
        ('confirmada', 'Confirmada'),
        ('em_andamento', 'Em Andamento'),
        ('cancelada', 'Cancelada'),
        ('finalizada', 'Finalizada')
    )

    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name="caronas"
    )

    origin = models.CharField(max_length=255)

    destination = models.CharField(max_length=255)

    expected_arrival = models.DateTimeField()

    start_time = models.DateTimeField()

    end_time = models.DateTimeField(
        null=True,
        blank=True
    )

    available_seats = models.IntegerField()

    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES
    )

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    # ==========================================
    # VALIDAÇÕES
    # ==========================================
    def clean(self):

        # limite de assentos
        if self.available_seats > self.vehicle.seats:
            raise ValidationError(
                f"O veículo possui apenas {self.vehicle.seats} assentos."
            )

        # horário final maior que inicial
        if self.end_time and self.end_time <= self.start_time:
            raise ValidationError(
                "O horário final deve ser maior que o horário inicial."
            )

        # previsão chegada maior que saída
        if self.expected_arrival <= self.start_time:
            raise ValidationError(
                "A previsão de chegada deve ser após a saída."
            )

    # ==========================================
    # SAVE
    # ==========================================
    def save(self, *args, **kwargs):

        self.clean()

        # muda automaticamente status
        if (
            timezone.now() >= self.start_time
            and self.status == 'confirmada'
        ):
            self.status = 'em_andamento'

        # impede motorista em duas viagens ao mesmo tempo
        conflito = Ride.objects.filter(
            vehicle__user=self.vehicle.user,
            status='em_andamento'
        ).exclude(pk=self.pk)

        if conflito.exists():
            raise ValidationError(
                "O motorista já possui uma carona em andamento."
            )

        # validações em update
        if self.pk:

            orig = Ride.objects.get(pk=self.pk)

            # corrida cancelada não altera
            if orig.status == 'cancelada':
                raise ValidationError(
                    "Corridas canceladas não podem ser alteradas."
                )

            # não altera preço se houver reservas
            if self.price != orig.price:

                if self.reservations.exists():

                    raise ValidationError(
                        "O preço não pode ser alterado pois já existem reservas para esta corrida."
                    )

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.origin} -> {self.destination}"


# ==========================================
# RESERVATION
# ==========================================
class Reservation(BaseModelWithSoftDelete):

    ride = models.ForeignKey(
        Ride,
        on_delete=models.CASCADE,
        related_name="reservations"
    )

    passenger = models.ManyToManyField(
        UserClient,
        related_name="reservations"
    )

    status = models.CharField(max_length=50)

    class Meta:
        verbose_name = "Reserva"
        verbose_name_plural = "Reservas"

    def __str__(self):
        return f"Reserva {self.uuid}"