import uuid
from datetime import timedelta

from django.db import models, transaction
from django.db.models import F
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.utils import timezone

from easyaudit.models import CRUDEvent

from .manager import SoftDeleteManager


def get_sentinel_user_client():
    from core.models import UserClient

    sentinel_id = uuid.UUID(int=0)

    client, _ = UserClient.objects.get_or_create(
        id=sentinel_id,
        defaults={'name': 'Deleted User Client'}
    )

    return client


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


class TimeStampedModel(CreatedAtMixin, UpdatedAtMixin):

    class Meta:
        abstract = True


class UserTrackedModel(CreatedByMixin, UpdatedByMixin):

    class Meta:
        abstract = True


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


class UserClient(TimeStampedModel):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    name = models.CharField(max_length=255, default='Unknown')

    is_driver = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class BaseModel(UUIDModel, TimeStampedModel, UserTrackedModel):

    class Meta:
        abstract = True


class BaseModelWithSoftDelete(BaseModel, SoftDeleteModel):

    class Meta:
        abstract = True


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

    def clean(self):
        now = timezone.now()

        if self.expected_arrival and self.expected_arrival < now:
            raise ValidationError(
                "A previsão de chegada não pode ser uma data passada."
            )

        if self.expected_arrival and self.expected_arrival > (now + timedelta(days=90)):
            raise ValidationError(
                "A previsão de chegada não pode ultrapassar 3 meses a partir de hoje."
            )

        if self.available_seats > self.vehicle.seats:
            raise ValidationError(
                f"O veículo possui apenas {self.vehicle.seats} assentos."
            )

        if self.end_time and self.end_time <= self.start_time:
            raise ValidationError(
                "O horário final deve ser maior que o horário inicial."
            )

        if self.expected_arrival and self.expected_arrival <= self.start_time:
            raise ValidationError(
                "A previsão de chegada deve ser após a saída."
            )

    def save(self, *args, **kwargs):
        self.full_clean()

        if timezone.now() >= self.start_time and self.status == 'confirmada':
            self.status = 'em_andamento'

        conflict = Ride.objects.filter(
            vehicle__user=self.vehicle.user,
            status='em_andamento'
        ).exclude(pk=self.pk)

        if conflict.exists():
            raise ValidationError(
                "O motorista já possui uma carona em andamento."
            )

        if self.pk:
            orig = Ride.objects.get(pk=self.pk)

            if orig.status == 'cancelada':
                raise ValidationError(
                    "Corridas canceladas não podem ser alteradas."
                )

            if self.price != orig.price:
                if self.reservations.exists():
                    raise ValidationError(
                        "O preço não pode ser alterado pois já existem reservas para esta corrida."
                    )

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.origin} -> {self.destination}"


class Reservation(BaseModelWithSoftDelete):

    STATUS_CHOICES = (
        ('pendente', 'Pendente'),
        ('confirmada', 'Confirmada'),
        ('cancelada', 'Cancelada'),
    )

    ride = models.ForeignKey(
        Ride,
        on_delete=models.CASCADE,
        related_name="reservations"
    )

    passenger = models.ForeignKey(
        UserClient,
        on_delete=models.CASCADE,
        related_name="reservations"
    )

    requested_seats = models.PositiveIntegerField(default=1)

    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES
    )

    class Meta:
        verbose_name = "Reserva"
        verbose_name_plural = "Reservas"

    def clean(self):
        if self.requested_seats <= 0:
            raise ValidationError(
                "A reserva deve ser de pelo menos 1 assento."
            )

    @transaction.atomic
    def save(self, *args, **kwargs):
        self.full_clean()

        nova_reserva = self.pk is None

        if nova_reserva:
            ride = Ride.objects.get(pk=self.ride.pk)

            if ride.available_seats < self.requested_seats:
                raise ValidationError(
                    f"Vagas insuficientes. Você pediu {self.requested_seats}, mas só há {ride.available_seats} disponíveis."
                )

            Ride.objects.filter(pk=self.ride.pk).update(
                available_seats=F('available_seats') - self.requested_seats
            )

            self.ride.refresh_from_db()

        else:
            reserva_antiga = Reservation.objects.get(pk=self.pk)

            if self.requested_seats != reserva_antiga.requested_seats:
                raise ValidationError(
                    "Não é possível alterar a quantidade de vagas de uma reserva existente."
                )

            if (
                reserva_antiga.status != 'cancelada'
                and self.status == 'cancelada'
            ):
                Ride.objects.filter(pk=self.ride.pk).update(
                    available_seats=F('available_seats') + self.requested_seats
                )

                self.ride.refresh_from_db()

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Reserva {self.pk} ({self.requested_seats} vagas) - {self.passenger.name}"


class UserClientAudit(CRUDEvent):

    class Meta:
        proxy = True
        verbose_name = 'Auditoria de UserClient'
        verbose_name_plural = 'Auditorias de UserClient'


class VehicleAudit(CRUDEvent):

    class Meta:
        proxy = True
        verbose_name = 'Auditoria de Veículo'
        verbose_name_plural = 'Auditorias de Veículos'


class RideAudit(CRUDEvent):

    class Meta:
        proxy = True
        verbose_name = 'Auditoria de Carona'
        verbose_name_plural = 'Auditorias de Caronas'


class ReservationAudit(CRUDEvent):

    class Meta:
        proxy = True
        verbose_name = 'Auditoria de Reserva'
        verbose_name_plural = 'Auditorias de Reservas'