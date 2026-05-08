from ..models import Reservation,Ride,Vehicle,UserClient
from rest_framework import serializers
from django.core.exceptions import ValidationError
from ..models import Reservation, Ride, Vehicle, UserClient


class UserClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserClient
        fields = 'name'

class ReservationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reservation
        fields = '__all__'


class RideSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ride
        fields = ['vehicle', 'origin', 'destination', 'start_time', 'end_time','expected_arrival','available_seats', 'status', 'price']
    
    def validate(self,data):
        vehicle = data['vehicle']
        available_seats = data['available_seats']

        if available_seats > vehicle.seats:
            raise serializers.ValidationError(
                {
                    "available_seats":
                    f"O veículo possui apenas {vehicle.seats} assentos."
                }
            )
        return data

class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = ['user', 'model', 'color', 'plate','seats']