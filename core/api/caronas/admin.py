from django.contrib import admin
from .models import UserClient,Veiculo,Carona,Reserva

admin.site.register(UserClient)
admin.site.register(Veiculo)
admin.site.register(Carona)
admin.site.register(Reserva)