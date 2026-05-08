from ..models import Reservation,Ride,Vehicle,UserClient
from rest_framework import serializers

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
        fields = ['vehicle', 'origin', 'destination', 'start_time', 'end_time','seats', 'status', 'price']

class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = ['user', 'model', 'color', 'plate']