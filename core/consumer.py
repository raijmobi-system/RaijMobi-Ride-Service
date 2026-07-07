# ride_service/core/consumer.py
import sys
import os
import json
import logging
import time

# 1. Ajusta o diretório raiz do projeto ao path primeiro
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django
from kafka import KafkaConsumer

# 2. Configura e inicializa o Django antes de QUALQUER import de models
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ride_service.settings')
django.setup()

# 3. AGORA SIM, importa o modelo local de forma segura
from core.models import UserClient   

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'kafka-user:9092')
TOPIC = 'user-events'
GROUP_ID = 'ride-service-v3'          

logger.info("Consumer do ride-service iniciado. Tentando conectar ao Kafka...")

max_retries = 30
consumer = None
for attempt in range(1, max_retries + 1):
    try:
        consumer = KafkaConsumer(
            TOPIC,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            group_id=GROUP_ID,
            auto_offset_reset='earliest',          
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
            
            # Ajuste preventivo: Se o user_service enviar 'is_driver', use direto.
            # Caso envie apenas 'is_rider', mantemos a conversão, mas com cuidado.
            is_driver = user_data.get('is_driver', None)
            if is_driver is None:
                is_rider = user_data.get('is_rider', False)
                is_driver = not is_rider

            # Atualiza ou cria o registro no banco local do ride_service
            obj, created = UserClient.objects.update_or_create(
                id=user_id,
                defaults={
                    'name': name,
                    'is_driver': is_driver   
                }
            )
            status = 'criado' if created else 'atualizado'
            logger.info("Usuário %s (%s) %s com sucesso via Kafka.", user_id, name, status)
        except Exception as e:
            logger.exception("Erro ao processar mensagem: %s", e)
except KeyboardInterrupt:
    logger.info("Consumer do ride-service encerrado.")