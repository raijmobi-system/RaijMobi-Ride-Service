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


class VehicleSerializer(serializers.ModelSerializer):
    # Mudamos para read_only=True para o DRF não exigir isso no POST
    class Meta:
        model = Vehicle
        fields = ['id', 'uuid', 'user', 'model', 'type_vehicle', 'color', 'plate', 'seats','photo']
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
    # 🌟 AQUI ESTÁ A SOLUÇÃO DEFINITIVA:
    # Dizemos ao Django: "Quando o frontend enviar o campo 'vehicle', não procure por ID numérico.
    # Procure na coluna 'uuid' da tabela de Veículos!"
    vehicle = serializers.SlugRelatedField(
        slug_field='uuid',
        queryset=Vehicle.objects.all()
    )

    class Meta:
        model = Ride
        fields = [
            'id',               # Pode manter o ID aqui, ele serve para o front ler (read-only) se quiser.
            'uuid',             # UUID da própria carona
            'vehicle',          # Agora aceita e valida pelo UUID do veículo!
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
        # Como usamos o SlugRelatedField acima, o 'value' aqui já chega como o OBJETO Vehicle correto!
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

        # Verifica se a previsão de chegada é após a partida
        if expected_arrival and expected_arrival <= start_time:
            raise serializers.ValidationError({
                "expected_arrival": "A previsão de chegada deve ser após a saída."
            })

        # Atualização automática do status se a partida já tiver ocorrido
        if start_time and timezone.now() >= start_time:
            data['status'] = 'em_andamento'
        else:
            data['status'] = 'pendente'

        # 🌟 CORREÇÃO: Busca por sobreposição exata de horários!
        # Só bloqueia se o motorista tiver uma carona ativa (pendente, confirmada ou em andamento)
        # que cruze exatamente com a janela [start_time -> expected_arrival] solicitada.
        conflitos_de_horario = Ride.objects.filter(
            vehicle__user=user,
            status__in=['pendente', 'confirmada', 'em_andamento'],
            start_time__lt=expected_arrival,     # Saída existente começa ANTES da nova chegar
            expected_arrival__gt=start_time      # Chegada existente termina DEPOIS da nova sair
        )

        # Se for um PATCH/PUT (atualização), ignora a própria carona na verificação
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
    # 🌟 ADICIONE ESTA LINHA PARA TRATAR O UUID DA CARONA:
    ride = serializers.SlugRelatedField(
        slug_field='uuid',
        queryset=Ride.objects.all()
    )

    class Meta:
        model = Reservation
        fields = ['id', 'ride', 'passenger', 'requested_seats', 'status']
        # 👇 ADICIONE ESTA LINHA:
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
        # Só verifica vagas na criação (POST)
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
        # Substitui a string do UUID pelo JSON completo do RideSerializer
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