from django.utils import timezone
from rest_framework import serializers

from ..models import Reservation, Ride, UserClient, Vehicle, Rating


class UserClientSerializer(serializers.ModelSerializer):

    is_suspended = serializers.ReadOnlyField()

    class Meta:
        model = UserClient
        fields = [
            'id', 
            'name', 
            'is_driver',
            'average_rating',
            'warning_count',
            'suspension_until',
            'is_suspended'
            ]


class ReservationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reservation
        fields = [
            'id',
            'ride',
            'passenger',
            'requested_seats',
            'status'
        ]

    def validate_passenger(self, value):
        if not UserClient.objects.filter(id=value.id).exists():
            raise serializers.ValidationError("Usuário não encontrado.")
        return value

    def validate_status(self, value):
        valid_status = ['pendente', 'confirmada', 'cancelada']
        if value not in valid_status:
            raise serializers.ValidationError("Status inválido.")
        return value
    
    def validate_passenger(self,value):

        if value.is_suspended:
            raise serializers.ValidationError(
                "Usuário suspenso temporariamente."
            )
        
        return value



    def validate(self, data):
        # Só verifica vagas na criação (POST)
        if self.instance is None:
            ride = data.get('ride')
            requested_seats = data.get('requested_seats', 1)
            if ride and ride.available_seats < requested_seats:
                raise serializers.ValidationError({
                    "requested_seats": f"A carona possui apenas {ride.available_seats} vagas disponíveis."
                })
        return data

class RideSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ride
        fields = [
            'id',
            'uuid',
            'vehicle',
            'origin',
            'destination',
            'start_time',
            'end_time',
            'expected_arrival',
            'available_seats',
            'status',
            'price'
        ]

    def validate_vehicle(self, value):
        if not UserClient.objects.filter(id=value.user.id).exists():
            raise serializers.ValidationError("Usuário do veículo não existe.")
        if not value.user.is_driver:
            raise serializers.ValidationError("Esse usuário não é motorista.")
        return value

    def validate(self, data):
        vehicle = data['vehicle']
        user = vehicle.user
        available_seats = data['available_seats']
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        expected_arrival = data.get('expected_arrival')

        if not user.can_create_ride():
         raise serializers.ValidationError(
            "Limite de caronas ativas atingido para este motorista."
        )

        if available_seats > vehicle.seats:
            raise serializers.ValidationError({
                "available_seats": f"O veículo possui apenas {vehicle.seats} assentos."
            })

        if end_time and end_time <= start_time:
            raise serializers.ValidationError({
                "end_time": "O horário final deve ser maior que o horário inicial."
            })

        if expected_arrival and expected_arrival <= start_time:
            raise serializers.ValidationError({
                "expected_arrival": "A previsão de chegada deve ser após a saída."
            })

        # Atualização automática do status se a partida já tiver ocorrido
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
                "vehicle": "O motorista já possui uma carona em andamento."
            })

        return data


class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = [
            'id',
            'user',
            'model',
            'type_vehicle',
            'color',
            'plate',
            'seats'
        ]

    def validate_user(self, value):
        if not UserClient.objects.filter(id=value.id).exists():
            raise serializers.ValidationError("Usuário não encontrado.")
        if not value.is_driver:
            raise serializers.ValidationError("O usuário não é motorista.")
        return value
    
    def validate(self,data):

        type_vehicle = data.get('type_vehicle')
        seats = data.get('seats')

        if type_vehicle == 'moto' and seats > 2:
            raise serializers.ValidationError({
                "seats: Moto pode ter no máximo 2 assentos."
            })
        
        if seats <= 0:
            raise serializers.ValidationError({
                "seats": "O veículo deve possuir pelo menos 1 assento."
            })
        return data
    
class RatingSerializer(serializers.ModelSerializer):

    evaluator_name = serializers.CharField(
        source='evaluator.name',
        read_only=True
    )

    evaluated_name = serializers.CharField(
        source='evaluated.name',
        read_only=True
    )

    class Meta:
        model = Rating
        fields = [
            'id',
            'reservation',
            'evaluator',
            'evaluator_name',
            'evaluated',
            'evaluated_name',
            'score',
        ]
        def validate_score(self,value):

            if value < 0 or value >5:
                raise serializers.ValidationError(
                    "A nota deve estar entre 1 e 5 estrelas."
                )
            
            return value