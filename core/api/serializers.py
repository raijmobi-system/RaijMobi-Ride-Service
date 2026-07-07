from django.utils import timezone
from rest_framework import serializers

from ..models import Reservation, Ride, UserClient, Vehicle, Rating


class UserClientSerializer(serializers.ModelSerializer):
    is_suspended = serializers.ReadOnlyField()

    class Meta:
        model = UserClient
        fields = [
            'id', # Agora é um UUID nativamente
            'name',
            'is_driver',
            'average_rating',
            'warning_count',
            'suspension_until',
            'is_suspended'
        ]


class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        # Removemos o 'uuid' daqui. O 'id' já é o UUID do veículo.
        fields = ['id', 'user', 'model', 'type_vehicle', 'color', 'plate', 'seats', 'photo']
        read_only_fields = ['user']

    def validate_user(self, value):
        if not UserClient.objects.filter(id=value.id).exists():
            raise serializers.ValidationError("Usuário não encontrado.")
        if not value.is_driver:
            raise serializers.ValidationError("O usuário não é motorista.")
        return value

    def validate(self, data):
        type_vehicle = data.get('type_vehicle')
        seats = data.get('seats')

        if type_vehicle is not None and seats is not None:
            if type_vehicle == 'moto' and seats > 2:
                raise serializers.ValidationError({
                    "seats": "Moto pode ter no máximo 2 assentos."
                })

        if seats is not None and seats <= 0:
            raise serializers.ValidationError({
                "seats": "O veículo deve possuir pelo menos 1 assento."
            })

        return data


class RideSerializer(serializers.ModelSerializer):
    # 🌟 SlugRelatedField FOI REMOVIDO! 
    # O DRF agora sabe que 'vehicle' recebe um UUID automaticamente porque o modelo exige isso.

    class Meta:
        model = Ride
        fields = [
            'id',               # O ID agora é o UUID da própria carona
            'vehicle',          # Espera e valida o UUID do veículo nativamente
            'origin',
            'destination',
            'start_time',
            'expected_arrival',
            'available_seats',
            'status',
            'price'
        ]
        read_only_fields = ['status']

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
        expected_arrival = data.get('expected_arrival')

        if not user.can_create_ride():
            raise serializers.ValidationError(
                "Limite de caronas ativas atingido para este motorista."
            )

        if available_seats > vehicle.seats:
            raise serializers.ValidationError({
                "available_seats": f"O veículo possui apenas {vehicle.seats} assentos."
            })

        if expected_arrival and expected_arrival <= start_time:
            raise serializers.ValidationError({
                "expected_arrival": "A previsão de chegada deve ser após a saída."
            })

        if start_time and timezone.now() >= start_time:
            data['status'] = 'em_andamento'
        else:
            data['status'] = 'pendente'

        conflitos_de_horario = Ride.objects.filter(
            vehicle__user=user,
            status__in=['pendente', 'confirmada', 'em_andamento'],
            start_time__lt=expected_arrival,     
            expected_arrival__gt=start_time      
        )

        if self.instance:
            # self.instance.pk continua funcionando perfeitamente (o pk aponta pro UUID agora)
            conflitos_de_horario = conflitos_de_horario.exclude(pk=self.instance.pk)

        if conflitos_de_horario.exists():
            carona_conflito = conflitos_de_horario.first()
            saida_fmt = carona_conflito.start_time.strftime('%d/%m às %H:%M')
            chegada_fmt = carona_conflito.expected_arrival.strftime('%d/%m às %H:%M')
            
            raise serializers.ValidationError({
                "start_time": f"Conflito de horário! Você já possui uma carona programada das {saida_fmt} até as {chegada_fmt}."
            })

        return data


class ReservationSerializer(serializers.ModelSerializer):
    # 🌟 SlugRelatedField FOI REMOVIDO AQUI TAMBÉM!

    class Meta:
        model = Reservation
        fields = ['id', 'ride', 'passenger', 'requested_seats', 'status']
        read_only_fields = ['id', 'passenger', 'status']

    def validate_passenger(self, value):
        if not UserClient.objects.filter(id=value.id).exists():
            raise serializers.ValidationError("Usuário não encontrado.")
        if value.is_suspended:
            raise serializers.ValidationError(
                "Usuário suspenso temporariamente."
            )
        if not value.can_make_reservation():
            raise serializers.ValidationError(
                "Limite de reservas ativas atingido."
            )
        return value

    def validate_status(self, value):
        valid_status = ['pendente', 'confirmada', 'cancelada']
        if value not in valid_status:
            raise serializers.ValidationError("Status inválido.")
        return value

    def validate(self, data):
        if self.instance is None:
            ride = data.get('ride')
            requested_seats = data.get('requested_seats', 1)
            if ride and ride.available_seats < requested_seats:
                raise serializers.ValidationError({
                    "requested_seats": f"A carona possui apenas {ride.available_seats} vagas disponíveis."
                })
        return data

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret['ride'] = RideSerializer(instance.ride, context=self.context).data
        return ret


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

    def validate_score(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError(
                "A nota deve estar entre 1 e 5 estrelas."
            )
        return value