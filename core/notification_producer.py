import json
import logging
from kafka import KafkaProducer
from django.conf import settings

logger = logging.getLogger(__name__)
producer = None

def get_producer():
    global producer
    if producer is None:
        try:
            producer = KafkaProducer(
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS_RIDE,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
            )
        except Exception as e:
            logger.error("Falha ao criar produtor Kafka: %s", e)
    return producer

def send_ride_notification(user_id, message):
    prod = get_producer()
    if prod is None:
        logger.warning("Produtor não disponível, notificação não enviada.")
        return
    data = {
        'user_id': str(user_id),
        'message': message,
    }
    try:
        future = prod.send('ride_notifications', key=str(user_id), value=data)
        future.get(timeout=5)
        logger.info("Notificação enviada para usuário %s: %s", user_id, message)
    except Exception as e:
        logger.error("Falha ao enviar notificação: %s", e)