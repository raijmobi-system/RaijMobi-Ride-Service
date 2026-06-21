import uuid
from datetime import timedelta
from django.db import models, transaction
from django.db.models import F, Avg
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from easyaudit.models import CRUDEvent
from .manager import SoftDeleteManager
from .notification_producer import send_ride_notification
from .metrics import rides_total,reservations_total,cancelations_total

# ==========================
# SENTINELA
# ==========================
def get_sentinel_user_client():
    from core.models import UserClient
    user, _ = UserClient.objects.get_or_create(
        id=uuid.UUID(int=0), 
        defaults={"name": "Deleted User Client"}
    )
    return user

# ==========================
# MIXINS
# ==========================
class CreatedAtMixin(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    class Meta: abstract = True

class UpdatedAtMixin(models.Model):
    updated_at = models.DateTimeField(auto_now=True)
    class Meta: abstract = True

class CreatedByMixin(models.Model):
    created_by = models.ForeignKey("core.UserClient", on_delete=models.SET(get_sentinel_user_client), null=True, related_name="created_%(class)s")
    class Meta: abstract = True

class UpdatedByMixin(models.Model):
    updated_by = models.ForeignKey("core.UserClient", on_delete=models.SET(get_sentinel_user_client), null=True, related_name="updated_%(class)s")
    class Meta: abstract = True

class TimeStampedModel(CreatedAtMixin, UpdatedAtMixin):
    class Meta: abstract = True

class UserTrackedModel(CreatedByMixin, UpdatedByMixin):
    class Meta: abstract = True

# ==========================
# BASE MODELS
# ==========================
class UUIDModel(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    class Meta: abstract = True

class SoftDeleteModel(models.Model):
    is_deleted = models.BooleanField(default=False)
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    def delete(self, *args, **kwargs):
        self.is_deleted = True
        self.save()

    class Meta: abstract = True

class BaseModel(UUIDModel, TimeStampedModel, UserTrackedModel):
    class Meta: abstract = True

class BaseModelWithSoftDelete(BaseModel, SoftDeleteModel):
    class Meta: abstract = True

# ==========================
# USER
# ==========================
class UserClient(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    is_driver = models.BooleanField(default=False)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    average_rating_update_at = models.DateTimeField(null=True, blank=True)
    warning_count = models.PositiveIntegerField(default=0)
    suspension_until = models.DateTimeField(null=True, blank=True)
    MAX_ACTIVE_RIDES = 3
    MAX_ACTIVE_RESERVATIONS = 3

    @property
    def is_suspended(self):
        return self.suspension_until and self.suspension_until > timezone.now()

    def can_create_ride(self):
        active = Ride.objects.filter(
            vehicle__user=self, 
            status__in=["pendente", "confirmada", "em_andamento"]
        ).count()
        return active < self.MAX_ACTIVE_RIDES

    def can_make_reservation(self):
        active = self.reservations.filter(status__in=["pendente", "confirmada"]).count()
        return active < self.MAX_ACTIVE_RESERVATIONS

    def register_cancelation(self):
        self.warning_count += 1
        if self.warning_count >= 5:
            self.suspension_until = timezone.now() + timedelta(days=7)
        self.save(update_fields=["warning_count", "suspension_until"])

    def recalculate_average_rating(self):
        self.average_rating = self.ratings_received.aggregate(avg=Avg("score"))["avg"] or 0
        self.average_rating_update_at = timezone.now()
        self.save(update_fields=["average_rating", "average_rating_update_at"])

    def __str__(self):
        return self.name

# ==========================
# VEHICLE
# ==========================
class Vehicle(BaseModelWithSoftDelete):
    TIPO_CHOICES = (("carro", "Carro"), ("moto", "Moto"))
    CORES_CHOICES = (("preto", "Preto"), ("branco", "Branco"), ("vermelho", "Vermelho"), ("azul", "Azul"))
    user = models.ForeignKey(UserClient, related_name="veiculos", on_delete=models.CASCADE)
    model = models.CharField(max_length=100)
    type_vehicle = models.CharField(max_length=20, choices=TIPO_CHOICES)
    color = models.CharField(max_length=50, choices=CORES_CHOICES)
    plate = models.CharField(max_length=10)
    seats = models.IntegerField()

    def clean(self):
        if self.seats <= 0:
            raise ValidationError("Veículo precisa possuir assentos.")
        if self.type_vehicle == "moto" and self.seats > 2:
            raise ValidationError("Moto possui limite de 2 assentos.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.model} - {self.plate}"

# ==========================
# RIDE
# ==========================
class Ride(BaseModelWithSoftDelete):
    STATUS_CHOICES = (("pendente", "Pendente"), ("confirmada", "Confirmada"), ("em_andamento", "Em andamento"), ("cancelada", "Cancelada"), ("finalizada", "Finalizada"))
    vehicle = models.ForeignKey(Vehicle, related_name="caronas", on_delete=models.CASCADE)
    origin = models.CharField(max_length=255)
    destination = models.CharField(max_length=255)
    start_time = models.DateTimeField()
    expected_arrival = models.DateTimeField()
    available_seats = models.IntegerField()
    status = models.CharField(max_length=30, choices=STATUS_CHOICES)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def clean(self):
        if self.available_seats > self.vehicle.seats:
            raise ValidationError("Quantidade de vagas inválida.")
        if self.expected_arrival <= self.start_time:
            raise ValidationError("Chegada deve ser depois da saída.")

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        self.clean()
        super().save(*args, **kwargs)

        if is_new:
            rides_total.inc()

    def __str__(self):
        return f"{self.origin} -> {self.destination}"

# ==========================
# RESERVATION
# ==========================
class Reservation(BaseModelWithSoftDelete):
    STATUS_CHOICES = (("pendente", "Pendente"), ("confirmada", "Confirmada"), ("cancelada", "Cancelada"))
    ride = models.ForeignKey(Ride, related_name="reservations", on_delete=models.CASCADE)
    passenger = models.ForeignKey(UserClient, related_name="reservations", on_delete=models.CASCADE)
    requested_seats = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES)

    class Meta: verbose_name = "Reserva"; verbose_name_plural = "Reservas"

    def clean(self):
        if self.requested_seats <= 0:
            raise ValidationError("A reserva deve possuir pelo menos 1 vaga.")

    @transaction.atomic
    def save(self, *args, **kwargs):
        if is_new:
           reservations_total.inc()

        is_new = self.pk is None
        old_status = None

        if not is_new:
            reserva_antiga = Reservation.objects.get(pk=self.pk)
            old_status = reserva_antiga.status
            
            if reserva_antiga.status != "cancelada" and self.status == "cancelada":
                cancelations_total.inc()
                if self.ride.status in ["em_andamento", "finalizada"]:
                    raise ValidationError("Não é possível cancelar esta carona.")
                
                Ride.objects.filter(pk=self.ride.pk).update(available_seats=F("available_seats") + self.requested_seats)
                self.passenger.register_cancelation()
        else:
            ride = Ride.objects.select_for_update().get(pk=self.ride.pk)
            if ride.available_seats < self.requested_seats:
                raise ValidationError(f"Não existem vagas suficientes. Restam apenas {ride.available_seats}.")
            
            Ride.objects.filter(pk=ride.pk).update(available_seats=F("available_seats") - self.requested_seats)

        super().save(*args, **kwargs)
        transaction.on_commit(lambda: self.send_notification(is_new, old_status))

    def send_notification(self, is_new, old_status):
        motorista = self.ride.vehicle.user
        if is_new:
            send_ride_notification(motorista.id, "Nova solicitação de carona.")
        elif old_status != self.status:
            if self.status == "confirmada":
                send_ride_notification(self.passenger.id, "Sua reserva foi confirmada.")
            elif self.status == "cancelada":
                send_ride_notification(motorista.id, "Reserva cancelada.")
                send_ride_notification(self.passenger.id, "Sua reserva foi cancelada.")

    def __str__(self):
        return f"Reserva {self.id} - {self.passenger.name}"

# ==========================
# AUDITORIA
# ==========================
class UserClientAudit(CRUDEvent):
    class Meta: proxy = True; verbose_name = "Auditoria usuário"; verbose_name_plural = "Auditorias usuários"

class VehicleAudit(CRUDEvent):
    class Meta: proxy = True; verbose_name = "Auditoria veículo"; verbose_name_plural = "Auditorias veículos"

class RideAudit(CRUDEvent):
    class Meta: proxy = True; verbose_name = "Auditoria carona"; verbose_name_plural = "Auditorias caronas"

class ReservationAudit(CRUDEvent):
    class Meta: proxy = True; verbose_name = "Auditoria reserva"; verbose_name_plural = "Auditorias reservas"

# ==========================
# RATING
# ==========================
class Rating(BaseModelWithSoftDelete):
    reservation = models.ForeignKey(Reservation, related_name="ratings", on_delete=models.CASCADE)
    evaluator = models.ForeignKey(UserClient, related_name="ratings_given", on_delete=models.CASCADE)
    evaluated = models.ForeignKey(UserClient, related_name="ratings_received", on_delete=models.CASCADE)
    score = models.PositiveSmallIntegerField()

    def clean(self):
        if self.score < 1 or self.score > 5:
            raise ValidationError("Nota deve ser entre 1 e 5.")
        if self.evaluator == self.evaluated:
            raise ValidationError("Usuário não pode avaliar a si mesmo.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        self.evaluated.recalculate_average_rating()

    class Meta: constraints = [models.UniqueConstraint(fields=["reservation", "evaluator"], name="unique_rating_per_reservation")]

    def __str__(self):
        return f"{self.evaluator} -> {self.evaluated}"