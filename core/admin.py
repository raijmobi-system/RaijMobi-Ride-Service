from django.contrib import admin
from .models import Ride,Vehicle,Reservation,UserClient


admin.site.register(Ride)
admin.site.register(Vehicle)
admin.site.register(Reservation)
admin.site.register(UserClient)