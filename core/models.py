import uuid
from datetime import timedelta

from django.db import models, transaction
from django.db.models import F
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError

from easyaudit.models import CRUDEvent

from .manager import SoftDeleteManager

from django.db.models import Avg


# ==========================================
# 1. FUNÇÃO SENTINELA
# ==========================================
def get_sentinel_user_client():
    from core.models import UserClient

    sentinel_id = uuid.UUID(int=0)
    client, _ = UserClient.objects.get_or_create(
        id=sentinel_id,
        defaults={'name': 'Deleted User Client'}
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
    name = models.CharField(max_length=255, default='Unknown')
    is_driver = models.BooleanField(default=False)   # mantido do primeiro bloco

    average_rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0
    )

    average_rating_update_at = models.DateTimeField(
        null=True,
        blank=True
    )
    warning_count = models.PositiveIntegerField(default=0)

    suspension_until = models.DateTimeField(null=True,blank=True)

    MAX_ACTIVE_RESERVATIONS = 3

    MAX_ACTIVE_RIDES = 3

    @property
    def is_suspended(self):
        return(
            self.suspension_until
            and self.suspension_until > timezone.now()

        )
    def can_create_ride(self):
        from .models import Ride

        active_rides_count = Ride.objects.filter(
            vehicle__user=self,
            status__in=['pendente','confirmada','em_andamento']
        ).count()

        return active_rides_count < self.MAX_ACTIVE_RIDES
    
    def can_make_reservation(self):
        active_reservations = self.reservations.filter(
            status__in=['pendente', 'confirmada']
        ).count()

        return active_reservations < self.MAX_ACTIVE_RESERVATIONS


    def register_cancelation(self):

        self.warning_count += 1

        if self.warning_count >= 5:
            self.suspension_until = (
                timezone.now() +
                timedelta(days=7)
            )
        self.save(
            update_fields=[
                'warning_count',
                'suspension_until'
            ]
        )

    def recalculate_average_rating(self):

        media = (
            self.ratings_received.aggregate(
                media=Avg('score')
            )['media']
            or 0
        )

        self.average_rating = media
        self.average_rating_update_at = timezone.now()

        self.save(
            update_fields=[
                'average_rating',
                'average_rating_update_at'
            ]
        )

    def __str__(self):
        return self.name


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
# 7. VEHICLE (com type_vehicle e cores)
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

    TIPO_CHOICES = (
        ('carro', 'Carro'),
        ('moto', 'Moto'),
    )

    user = models.ForeignKey(
        UserClient,
        on_delete=models.CASCADE,
        related_name="veiculos"
    )
    model = models.CharField(max_length=100)
    type_vehicle = models.CharField(max_length=20, choices=TIPO_CHOICES)   # presente no primeiro bloco
    color = models.CharField(max_length=50, choices=CORES_CHOICES)
    plate = models.CharField(max_length=10)
    seats = models.IntegerField()

    def clean(self):

        if self.type_vehicle == 'moto' and self.seats > 2:
            raise ValidationError(
                "Moto pode ter no máximo 2 assentos."
            )
        
        if self.seats <= 0:
            raise ValidationError(
                "O veículo deve possuir pelo menos 1 assento."
            )
    
    def save(self,*args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.model} - {self.plate}"


# ==========================================
# 8. RIDE
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
    end_time = models.DateTimeField(null=True, blank=True)
    
    available_seats = models.IntegerField()
    status = models.CharField(max_length=50, choices=STATUS_CHOICES)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def clean(self):
        now = timezone.now()

        if self.expected_arrival and self.expected_arrival < now:
            raise ValidationError("A previsão de chegada não pode ser uma data passada.")

        if self.expected_arrival and self.expected_arrival > (now + timedelta(days=90)):
            raise ValidationError("A previsão de chegada não pode ultrapassar 3 meses a partir de hoje.")

        if self.available_seats > self.vehicle.seats:
            raise ValidationError(f"O veículo possui apenas {self.vehicle.seats} assentos.")

        if self.end_time and self.end_time <= self.start_time:
            raise ValidationError("O horário final deve ser maior que o horário inicial.")

        if self.expected_arrival and self.expected_arrival <= self.start_time:
            raise ValidationError("A previsão de chegada deve ser após a saída.")

    def save(self, *args, **kwargs):

        if timezone.now() >= self.start_time and self.status == 'confirmada':
            self.status = 'em_andamento'

        conflict = Ride.objects.filter(
            vehicle__user=self.vehicle.user,
            status='em_andamento'
        ).exclude(pk=self.pk)

        if conflict.exists():
            raise ValidationError("O motorista já possui uma carona em andamento.")

        if self.pk:
            orig = Ride.objects.get(pk=self.pk)
            if orig.status == 'cancelada':
                raise ValidationError("Corridas canceladas não podem ser alteradas.")
            if self.price != orig.price and self.reservations.exists():
                raise ValidationError("O preço não pode ser alterado pois já existem reservas para esta corrida.")

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.origin} -> {self.destination}"


# ==========================================
# 9. RESERVATION (com lógica fundida e Kafka opcional)
# ==========================================
class Reservation(BaseModelWithSoftDelete):
    STATUS_CHOICES = (
        ('pendente', 'Pendente'),
        ('confirmada', 'Confirmada'),
        ('cancelada', 'Cancelada'),
    )

    ride = models.ForeignKey(Ride, on_delete=models.CASCADE, related_name="reservations")
    passenger = models.ForeignKey(UserClient, on_delete=models.CASCADE, related_name="reservations")
    requested_seats = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES)

    class Meta:
        verbose_name = "Reserva"
        verbose_name_plural = "Reservas"

    def clean(self):
        if self.requested_seats <= 0:
            raise ValidationError("A reserva deve ser de pelo menos 1 assento.")


    @transaction.atomic
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        old_status = None
        if not is_new:
            old_status = Reservation.objects.get(pk=self.pk).status

        if is_new:
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
                    "Não é possível alterar a quantidade de vagas de uma reserva existente. "
                    "Por favor, cancele esta reserva e faça uma nova."
                )
            if reserva_antiga.status != 'cancelada' and self.status == 'cancelada':
                Ride.objects.filter(pk=self.ride.pk).update(
                    available_seats=F('available_seats') + self.requested_seats
                )

                self.passenger.register_cancelation()

                self.ride.refresh_from_db()

        super().save(*args, **kwargs)

        # Envio não‑crítico para o Kafka – falhas são apenas registadas
        if self.status == 'confirmada' and (is_new or old_status != 'confirmada'):
            try:
                from .kafka_producer import send_ride_event
                send_ride_event(self.ride)
            except ImportError:
                pass  # Kafka não instalado – não é erro
            except Exception as e:
                logger.warning("Falha ao enviar evento Kafka para a carona %s: %s", self.ride.uuid, e)

    def __str__(self):
        return f"Reserva {self.pk} ({self.requested_seats} vagas) - {self.passenger.name}"
    
    
    def __str__(self):
        return f"Reserva {self.pk} ({self.requested_seats} vagas) - {self.passenger.name}"


# ==========================================
# 10. AUDIT PROXIES (easyaudit)
# ==========================================
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

class Rating(BaseModelWithSoftDelete):

    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        related_name="ratings"
    )

    evaluator = models.ForeignKey(
        UserClient,
        on_delete=models.CASCADE,
        related_name="ratings_given"
    )

    evaluated = models.ForeignKey(
        UserClient,
        on_delete=models.CASCADE,
        related_name="ratings_received"
    )

    score =  models.PositiveSmallIntegerField()

    def clean(self):

        if self.score <1 or self.score > 5:
            raise ValidationError(
                "A nota deve estar entre 1 e 5 estrelas."
            )

        if self.evaluator == self.evaluated:
            raise ValidationError(
                "Um usuário não pode avaliar a si mesmo."
            )

    def save(self, *args, **kwargs):

        self.full_clean()

        is_new = self.pk is None

        first_rating = (
            is_new
            and not Rating.objects.filter(
                evaluated=self.evaluated
            ).exists()
        )

        super().save(*args, **kwargs)

        should_update = False

        if first_rating:
            should_update = True

        elif (
            self.evaluated.average_rating_update_at is None
            or timezone.now() - self.evaluated.average_rating_update_at >= timedelta(hours=12)
        ):
            should_update = True

        if should_update:
            self.evaluated.recalculate_average_rating()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['reservation', 'evaluator'],
                name='unique_rating_per_reservation'
            )
        ]

    def __str__(self):
        return (
            f"{self.evaluator} -> "
            f"{self.evaluated} "
            f"({self.score})"
        )