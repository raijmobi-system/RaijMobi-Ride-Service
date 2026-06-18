from rest_framework import serializers
from ..models import UserClient, Vehicle, Ride, Reservation, Rating

class UserClientSerializer(serializers.ModelSerializer):
    is_suspended = serializers.ReadOnlyField()

    class Meta:
        model = UserClient
        fields = ["id", "name", "is_driver", "average_rating", "warning_count", "suspension_until", "is_suspended"]

class VehicleSerializer(serializers.ModelSerializer):

    class Meta:
        model = Vehicle
        fields = ["id", "user", "model", "type_vehicle", "color", "plate", "seats"]

    def validate_user(self, value):
        if not value.is_driver:
            raise serializers.ValidationError("Usuário não é motorista.")
        return value

class RideSerializer(serializers.ModelSerializer):

    class Meta:
        model = Ride
        fields = ["id", "uuid", "vehicle", "origin", "destination", "start_time", "expected_arrival", "available_seats", "status", "price"]

    def validate(self, data):
        vehicle = data.get("vehicle")
        if not vehicle.user.can_create_ride():
            raise serializers.ValidationError("Motorista atingiu o limite de caronas ativas.")
        if data.get("available_seats") > vehicle.seats:
            raise serializers.ValidationError("Quantidade de vagas maior que a capacidade do veículo.")
        return data

class ReservationSerializer(serializers.ModelSerializer):

    class Meta:
        model = Reservation
        fields = ["id", "ride", "passenger", "requested_seats", "status"]

    def validate_passenger(self, value):
        if value.is_suspended:
            raise serializers.ValidationError("Usuário suspenso temporariamente.")
        if not value.can_make_reservation():
            raise serializers.ValidationError("Limite de reservas ativas atingido.")
        return value

    def validate(self, data):
        ride = data.get("ride")
        seats = data.get("requested_seats", 1)
        if ride.available_seats < seats:
            raise serializers.ValidationError({"requested_seats": "Não existem vagas suficientes."})
        return data

class RatingSerializer(serializers.ModelSerializer):
    evaluator_name = serializers.CharField(source="evaluator.name", read_only=True)
    evaluated_name = serializers.CharField(source="evaluated.name", read_only=True)

    class Meta:
        model = Rating
        fields = ["id", "reservation", "evaluator", "evaluator_name", "evaluated", "evaluated_name", "score"]

    def validate_score(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("A nota deve estar entre 1 e 5.")
        return value