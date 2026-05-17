# # chat_service/consumer.py
# import os
# import json
# from kafka import KafkaConsumer
# from django.conf import settings
# import django

# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
# django.setup()

# from chat_service.models import UserClient

# KAFKA_BOOTSTRAP_SERVERS = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'kafka-user:9092')
# TOPIC = 'user-events'

# consumer = KafkaConsumer(
#     TOPIC,
#     bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
#     group_id='chat-service',
#     auto_offset_reset='earliest',
#     value_deserializer=lambda v: json.loads(v.decode('utf-8')),
#     key_deserializer=lambda k: k.decode('utf-8') if k else None,
# )

# for message in consumer:
#     user_data = message.value
#     user_id = user_data['id']
#     name = user_data['name']
#     is_rider = user_data.get('is_rider', False)

#     # cria ou atualiza o UserClient local
#     UserClient.objects.update_or_create(
#         id=user_id,
#         defaults={
#             'name': name,
#             'is_rider': is_rider,
#         }
#     )

# ride_service/core/consumer.py
import sys
import os

# Adiciona o diretório raiz do projeto ao path
# para que 'ride_service.settings' seja encontrável
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import logging
from kafka import KafkaConsumer
import django

# ⚠️ Atenção: o settings module é ride_service.settings, e não core.settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ride_service.settings')
django.setup()

from core.models import UserClient   # importa o modelo local

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'kafka-user:9092')
TOPIC = 'user-events'

consumer = KafkaConsumer(
    TOPIC,
    bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
    group_id='ride-service',               # group_id único para este serviço
    auto_offset_reset='earliest',          # para ler também mensagens antigas durante testes
    value_deserializer=lambda v: json.loads(v.decode('utf-8')),
    key_deserializer=lambda k: k.decode('utf-8') if k else None,
)

logger.info("Consumer do ride-service iniciado. Aguardando mensagens no tópico %s", TOPIC)

try:
    for message in consumer:
        try:
            user_data = message.value
            user_id = user_data['id']
            name = user_data['name']
            is_rider = user_data.get('is_rider', False)

            obj, created = UserClient.objects.update_or_create(
                id=user_id,
                defaults={'name': name, 'is_rider': is_rider}
            )
            status = 'criado' if created else 'atualizado'
            logger.info("Usuário %s (%s) %s com sucesso.", user_id, name, status)
        except Exception as e:
            logger.exception("Erro ao processar mensagem: %s", e)
except KeyboardInterrupt:
    logger.info("Consumer do ride-service encerrado.")