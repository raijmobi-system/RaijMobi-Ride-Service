from django.contrib import admin
from .models import Ride,Vehicle,Reservation,UserClient


admin.site.register(Ride)
admin.site.register(Vehicle)
admin.site.register(Reservation)
admin.site.register(UserClient)


# core/admin.py
from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from .models import UserClient, Vehicle, Ride, Reservation  # modelos originais
from .models import UserClientAudit, VehicleAudit, RideAudit, ReservationAudit  # proxies (se definidos no models.py)

# Se você colocou os proxies em audit_models.py, importe de lá:
# from .audit_models import UserClientAudit, VehicleAudit, RideAudit, ReservationAudit


class UserClientAuditAdmin(admin.ModelAdmin):
    list_display = ('event_type', 'user', 'datetime', 'object_repr')
    list_filter = ('event_type', 'user', 'datetime')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        content_type = ContentType.objects.get_for_model(UserClient)
        return qs.filter(content_type=content_type)


class VehicleAuditAdmin(admin.ModelAdmin):
    list_display = ('event_type', 'user', 'datetime', 'object_repr')
    list_filter = ('event_type', 'user', 'datetime')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        content_type = ContentType.objects.get_for_model(Vehicle)
        return qs.filter(content_type=content_type)


class RideAuditAdmin(admin.ModelAdmin):
    list_display = ('event_type', 'user', 'datetime', 'object_repr')
    list_filter = ('event_type', 'user', 'datetime')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        content_type = ContentType.objects.get_for_model(Ride)
        return qs.filter(content_type=content_type)


class ReservationAuditAdmin(admin.ModelAdmin):
    list_display = ('event_type', 'user', 'datetime', 'object_repr')
    list_filter = ('event_type', 'user', 'datetime')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        content_type = ContentType.objects.get_for_model(Reservation)
        return qs.filter(content_type=content_type)


admin.site.register(UserClientAudit, UserClientAuditAdmin)
admin.site.register(VehicleAudit, VehicleAuditAdmin)
admin.site.register(RideAudit, RideAuditAdmin)
admin.site.register(ReservationAudit, ReservationAuditAdmin)