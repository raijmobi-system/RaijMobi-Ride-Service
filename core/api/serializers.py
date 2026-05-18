from ..models import Reservation,Ride,Vehicle,UserClient
from rest_framework import serializers
from django.core.exceptions import ValidationError
from ..models import Reservation, Ride, Vehicle, UserClient
from django.utils import timezone


class UserClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserClient
        fields = 'name'

class ReservationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reservation
        fields = [
            'id',
            'ride',
            'passenger',
            'status'
        ]
    def validate_status(self,value):

        status_validos = [
            'pendente',
            'confirmada',
            'cancelada',
        ]

        if value not in status_validos:

            raise serializers.ValidationError(
                "Status inválido"
            )
        
        return value


class RideSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ride
        fields = ['id','uuid', 'vehicle', 'origin', 'destination', 'start_time', 'end_time','expected_arrival','available_seats', 'status', 'price']
    
    def validate(self,data):
        vehicle = data['vehicle']
        available_seats = data['available_seats']
        start_time = data.get('start_time')
        end_time = data.get('end_time')

        if available_seats > vehicle.seats:
            raise serializers.ValidationError(
                {
                    "available_seats":
                    f"O veículo possui apenas {vehicle.seats} assentos."
                }
            )
        if end_time and end_time <= start_time:
            raise serializers.ValidationError({
                "end_time":
                "O horário final deve ser maior que o horário inicial."
            })
        if timezone.now() >= start_time:
            data['status'] = 'em_andamento'

        conflito = Ride.objects.filter(
            vehicle__user=vehicle.user,
            status='em_andamento'
            )
        if self.instance:
            conflito = conflito.exclude(pk=self.instance.pk)

        if conflito.exists():

            raise serializers.ValidationError({
                "vehicle":
                "O motorista já possui uma carona em andamento."
            })
        

        return data

class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = ['id','user', 'model', 'color', 'plate','seats']