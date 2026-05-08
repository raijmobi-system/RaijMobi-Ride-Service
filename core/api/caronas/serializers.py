from rest_framework import serializers
from .models import Veiculo,Carona,Reserva

class VeiculoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Veiculo
        fields = '__all__'

class CaronaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Carona
        fields = '__all__'

class ReservaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reserva
        fields = '__all__'