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
    class Meta:
        model = Ride
        fields = [
            'id', 'vehicle', 'origin', 'destination',
            'start_time', 'expected_arrival', 'available_seats',
            'status', 'price'
        ]
        # 🌟 CORREÇÃO 1: Removemos 'status' de read_only_fields para aceitar PATCH/PUT
        read_only_fields = []  # Antes era: ['status']

    def validate_vehicle(self, value):
        if not UserClient.objects.filter(id=value.user.id).exists():
            raise serializers.ValidationError("Usuário do veículo não existe.")
        if not value.user.is_driver:
            raise serializers.ValidationError("Esse usuário não é motorista.")
        return value

    def validate(self, data):
        # Usamos getattr para resgatar valores da instância caso não venham no PATCH
        vehicle = data.get('vehicle', getattr(self.instance, 'vehicle', None))
        user = vehicle.user if vehicle else None
        available_seats = data.get('available_seats', getattr(self.instance, 'available_seats', 0))
        start_time = data.get('start_time', getattr(self.instance, 'start_time', None))
        expected_arrival = data.get('expected_arrival', getattr(self.instance, 'expected_arrival', None))

        # 🌟 CORREÇÃO 2: Só aplica regras iniciais de criação se self.instance for None!
        if self.instance is None:
            if not user.can_create_ride():
                raise serializers.ValidationError(
                    "Limite de caronas ativas atingido para este motorista."
                )

            # Define o status automático APENAS ao criar uma carona nova
            if start_time and timezone.now() >= start_time:
                data['status'] = 'em_andamento'
            else:
                data['status'] = 'pendente'
        else:
            # Se for atualização (PATCH/PUT), valida se o status enviado é legítimo
            if 'status' in data:
                valid_status = ['pendente', 'confirmada', 'em_andamento', 'finalizada', 'cancelada']
                if data['status'] not in valid_status:
                    raise serializers.ValidationError({"status": "Status de viagem inválido."})

        # Validações gerais que valem tanto para criação quanto edição
        if available_seats > vehicle.seats:
            raise serializers.ValidationError({
                "available_seats": f"O veículo possui apenas {vehicle.seats} assentos."
            })

        if expected_arrival and start_time and expected_arrival <= start_time:
            raise serializers.ValidationError({
                "expected_arrival": "A previsão de chegada deve ser após a saída."
            })

        conflitos_de_horario = Ride.objects.filter(
            vehicle__user=user,
            status__in=['pendente', 'confirmada', 'em_andamento'],
            start_time__lt=expected_arrival,     
            expected_arrival__gt=start_time      
        )

        if self.instance:
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

    class Meta:
        model = Reservation
        fields = ['id', 'ride', 'passenger', 'requested_seats', 'status']
        read_only_fields = ['id', 'passenger']

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