# ride_service/core/consumer.py
import sys
import os
import json
import logging
import time

# Adiciona o diretório raiz do projeto ao path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
GROUP_ID = 'ride-service-v3'          # grupo NOVO para forçar a leitura desde o início

logger.info("Consumer do ride-service iniciado. Tentando conectar ao Kafka...")

# Tenta conectar com retry (Kafka pode demorar para subir)
max_retries = 30
consumer = None
for attempt in range(1, max_retries + 1):
    try:
        consumer = KafkaConsumer(
            TOPIC,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            group_id=GROUP_ID,
            auto_offset_reset='earliest',          # ler mensagens antigas
            value_deserializer=lambda v: json.loads(v.decode('utf-8')),
            key_deserializer=lambda k: k.decode('utf-8') if k else None,
        )
        logger.info("Conectado ao Kafka com sucesso.")
        break
    except Exception as e:
        logger.warning(f"Tentativa {attempt}/{max_retries} falhou: {e}")
        time.sleep(2)
else:
    logger.error("Não foi possível conectar ao Kafka após várias tentativas.")
    sys.exit(1)

logger.info("Consumer do ride-service iniciado. Aguardando mensagens no tópico %s", TOPIC)

try:
    for message in consumer:
        try:
            user_data = message.value
            user_id = user_data['id']
            name = user_data['name']
            # O user-service envia 'is_rider' (true = passageiro)
            is_rider = user_data.get('is_rider', False)
            # Mapeia para o campo do modelo ride-service: is_driver
            obj, created = UserClient.objects.update_or_create(
                id=user_id,
                defaults={
                    'name': name,
                    'is_driver': not is_rider   # passageiro → is_driver=False, motorista → True
                }
            )
            status = 'criado' if created else 'atualizado'
            logger.info("Usuário %s (%s) %s com sucesso.", user_id, name, status)
        except Exception as e:
            logger.exception("Erro ao processar mensagem: %s", e)
except KeyboardInterrupt:
    logger.info("Consumer do ride-service encerrado.")