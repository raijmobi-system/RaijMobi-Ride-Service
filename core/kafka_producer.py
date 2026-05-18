import json
import logging
from kafka import KafkaProducer
from django.conf import settings

logger = logging.getLogger(__name__)

producer = KafkaProducer(
    bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS_RIDE,
    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
    key_serializer=lambda k: k.encode('utf-8') if k else None,
)

def send_ride_event(ride):
    """Envia evento de carona confirmada para o chat_service."""
    message = {
        'ride_id': str(ride.uuid),          # UUID da carona
        'driver_id': str(ride.vehicle.user.id),
        'origin': ride.origin,
        'destination': ride.destination,
        'start_time': ride.start_time.isoformat(),
        'price': str(ride.price),
        'available_seats': ride.available_seats,
        # passageiros iniciais (vazio – serão adicionados depois)
        'passengers': [],
    }
    future = producer.send('ride-events', key=str(ride.uuid), value=message)
    try:
        future.get(timeout=10)
        logger.info(f"Evento enviado para carona {ride.uuid}")
    except Exception as e:
        logger.error(f"Falha ao enviar evento: {e}")