

import json
import time
import logging
import re
from abc import ABC, abstractmethod

from django.conf import settings
from django.utils import timezone

from .models import Ride, Reservation
from .metrics import (
    ai_requests_total,
    ai_requests_failed_total,
    ai_recommendations_total,
    ai_filters_total,
    ai_response_time_seconds,
)

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# 1. Provedor de IA (Ollama)
# -------------------------------------------------------------------
class AIProvider(ABC):
    @abstractmethod
    def chat(self, prompt: str):
        """Envia o prompt e retorna a resposta (texto) ou dicionário."""
        ...


class OllamaProvider(AIProvider):
    def __init__(self):
        try:
            import requests
            self.requests = requests
        except ImportError:
            raise ImportError("Instale a biblioteca requests")
        self.base_url = getattr(settings, "OLLAMA_URL", "http://localhost:11434")
        self.model = getattr(settings, "OLLAMA_MODEL", "llama3")

    def chat(self, prompt):
        resp = self.requests.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            },
            timeout=(5, 90),
        )
        data = resp.json()
        
        # 🌟 CORREÇÃO DEFENSIVA: Verifica as variações comuns de resposta do Ollama
        if "message" in data and "content" in data["message"]:
            text = data["message"]["content"]
        elif "response" in data:
            text = data["response"]
        else:
            # Se vier num formato totalmente diferente, logamos para auditar e pegamos o texto cru
            logger.error(f"❌ Formato de resposta do Ollama inesperado: {data}")
            raise KeyError("Não foi possível encontrar a chave de resposta de texto ('message' ou 'response') no retorno da IA.")

        # Limpa marcações JSON (```json ... ```) e faz o parse
        return text

def get_ai_provider():
    return OllamaProvider()


# -------------------------------------------------------------------
# 2. Recomendador (AIRideRecommender)
# -------------------------------------------------------------------
class AIRideRecommender:
    def __init__(self):
        self.provider = get_ai_provider()
        self._cache = {}

    def recommend(self, user_id, top_n=5, history_limit=10):
        now = time.time()
        cache_key = str(user_id)
        cached = self._cache.get(cache_key)
        if cached and (now - cached["timestamp"]) < 300:
            return cached["data"]

        # ... (código existente do recomendador, mantido)
        recent_reservations = Reservation.objects.filter(
            passenger_id=user_id,
            status__in=["confirmada", "finalizada"],
            created_at__gte=timezone.now() - timezone.timedelta(days=90),
        ).select_related("ride__vehicle__user").order_by("-created_at")[:history_limit]

        if recent_reservations:
            history_text = "Histórico recente de viagens:\n"
            for i, res in enumerate(recent_reservations, 1):
                r = res.ride
                history_text += (
                    f"{i}. {r.origin} → {r.destination}, "
                    f"Partida: {r.start_time.strftime('%d/%m/%Y %H:%M')}, "
                    f"Preço: R$ {r.price}, Vagas pedidas: {res.requested_seats}, "
                    f"Motorista: {r.vehicle.user.name} (nota {r.vehicle.user.average_rating})\n"
                )
        else:
            history_text = "O usuário ainda não tem histórico de viagens.\n"

        active_rides = Ride.objects.filter(
            status__in=["pendente", "confirmada"],
            start_time__gte=timezone.now(),
        ).select_related("vehicle__user").order_by("start_time")

        if not active_rides:
            return []

        rides_text = "Caronas disponíveis agora:\n"
        ride_map = {}
        for idx, ride in enumerate(active_rides):
            rides_text += (
                f"Índice {idx}: {ride.origin} → {ride.destination}, "
                f"Partida: {ride.start_time.strftime('%d/%m/%Y %H:%M')}, "
                f"Vagas: {ride.available_seats}/{ride.vehicle.seats}, "
                f"Preço: R$ {ride.price}, "
                f"Motorista: {ride.vehicle.user.name} (nota {ride.vehicle.user.average_rating})\n"
            )
            ride_map[str(idx)] = ride.id

        prompt = f"""
Você é um assistente de recomendações para um aplicativo de caronas.
{history_text}

Com base nesse histórico (ou na falta dele), selecione as {top_n} melhores caronas disponíveis para o usuário.
Lista de caronas ativas:

{rides_text}

Escolha as que mais combinam com as preferências do usuário:
- Se houver histórico, priorize rotas semelhantes, faixa de preço habitual, horários compatíveis e motoristas bem avaliados.
- Se não houver histórico, use critérios gerais como menor preço, melhor avaliação do motorista, horários mais convenientes.

Responda **exclusivamente** com um array JSON no formato:
[
  {{ "index": "<índice da lista>", "reason": "breve justificativa (máx. 100 caracteres)" }}
]
Sem nenhum texto adicional.
"""
        ai_requests_total.inc()
        try:
            raw = self.provider.chat(prompt)
            # O provider retorna texto, precisamos parsear para JSON
            # O provider já limpou, mas vamos garantir
            try:
                recommendations = json.loads(raw)
            except json.JSONDecodeError:
                # Se falhar, tenta extrair apenas o JSON
                match = re.search(r'\[.*\]', raw, re.DOTALL)
                if match:
                    recommendations = json.loads(match.group())
                else:
                    raise
        except Exception as e:
            logger.error(f"Erro ao chamar IA para recomendações: {e}")
            return []

        result = []
        for rec in recommendations:
            idx = str(rec.get("index"))
            reason = rec.get("reason", "")
            if idx in ride_map:
                ride = Ride.objects.filter(id=ride_map[idx]).first()
                if ride:
                    result.append({"ride": ride, "reason": reason, "score": 0})

        if not result:
            return []

        self._cache[cache_key] = {"timestamp": now, "data": result[:top_n]}
        ai_recommendations_total.inc(len(result))
        return result[:top_n]


# -------------------------------------------------------------------
# 3. Extrator de filtros (AIFilterExtractor) – VERSÃO ÚNICA E COMPLETA
# -------------------------------------------------------------------
class AIFilterExtractor:
    def __init__(self):
        self.provider = get_ai_provider()

#     def extract_filters(self, text: str) -> dict:
#         # Inicializa com todos os campos None
#         filters = {
#             "origin": None,
#             "destination": None,
#             "price_min": None,
#             "price_max": None,
#             "vehicle_type": None,
#             "start_time_after": None,
#         }

#         # 1. Tenta extrair com IA
#         prompt = f"""
# Extraia os seguintes campos da frase do usuário, retornando APENAS o JSON.
# Campos:
# - "origin": local de partida (ou null)
# - "destination": local de destino (ou null)
# - "price_min": valor mínimo (ou null)
# - "price_max": valor máximo (ou null)
# - "vehicle_type": "carro" ou "moto" (ou null)
# - "start_time_after": data/hora (ou null)

# Texto: "{text}"

# Exemplo:
# "quero viajar do centro para o aeroporto amanhã, preço até 30 reais"
# → {{"origin": "Centro", "destination": "Aeroporto", "price_min": null, "price_max": 30, "vehicle_type": null, "start_time_after": null}}

# Retorne APENAS o JSON.
# """
#         ai_requests_total.inc()
#         try:
#             raw = self.provider.chat(prompt)
#             logger.info(f"Resposta bruta da IA (filtro): {raw[:200]}...")
#             # Tenta parsear JSON
#             try:
#                 ai_filters = json.loads(raw)
#             except json.JSONDecodeError:
#                 # Se falhar, tenta extrair { ... }
#                 match = re.search(r'\{.*\}', raw, re.DOTALL)
#                 if match:
#                     ai_filters = json.loads(match.group())
#                 else:
#                     raise
#             # Atualiza com os valores não nulos
#             for key in filters.keys():
#                 if key in ai_filters and ai_filters[key] is not None:
#                     filters[key] = ai_filters[key]
#         except Exception as e:
#             logger.error(f"Erro ao extrair filtros com IA: {e}")
#             # Continua com os filtros None, para que o fallback regex tente

#         # 2. Função para limpar localidades (remove artigos, preposições, verbos)
#         def clean_location(loc):
#             if not loc:
#                 return None
#             stopwords = ['quero', 'viajar', 'de', 'do', 'da', 'o', 'a', 'para', 'até',
#                          'amanhã', 'hoje', 'às', 'horas', 'em', 'no', 'na']
#             pattern = r'\b(' + '|'.join(stopwords) + r')\b'
#             cleaned = re.sub(pattern, '', loc, flags=re.IGNORECASE).strip()
#             cleaned = re.sub(r'\s+', ' ', cleaned).strip()
#             return cleaned if cleaned else None

#         # 3. Fallback para origem (regex)
#         origin_match = re.search(r'(?:de\s+|do\s+|da\s+)?([A-Za-zÀ-ÖØ-öø-ÿ\s]+?)\s+para\s+', text, re.IGNORECASE)
#         if origin_match:
#             origem = origin_match.group(1).strip()
#             origem = clean_location(origem)
#             if origem:
#                 filters['origin'] = ' '.join(word.capitalize() for word in origem.split())

#         # 4. Fallback para destino (regex)
#         dest_match = re.search(r'para\s+([A-Za-zÀ-ÖØ-öø-ÿ\s]+?)(?:\s+até|\s+amanhã|\s+às|\s*$)', text, re.IGNORECASE)
#         if dest_match:
#             destino = dest_match.group(1).strip()
#             destino = clean_location(destino)
#             if destino:
#                 filters['destination'] = ' '.join(word.capitalize() for word in destino.split())

#         # 5. Fallback para price_min
#         price_min_match = re.search(r'de\s*(\d+[,.]?\d*)\s*(?:reais)?', text, re.IGNORECASE)
#         if price_min_match:
#             filters['price_min'] = float(price_min_match.group(1).replace(',', '.'))

#         # 6. Fallback para price_max
#         if not filters.get('price_max'):
#             price_match = re.search(r'até\s*(\d+[,.]?\d*)', text, re.IGNORECASE)
#             if not price_match:
#                 price_match = re.search(r'(?:R?\$?)\s*(\d+[,.]?\d*)\s*(?:reais)?', text, re.IGNORECASE)
#             if price_match:
#                 filters['price_max'] = float(price_match.group(1).replace(',', '.'))

#         # 7. Fallback para vehicle_type
#         if not filters.get('vehicle_type'):
#             if re.search(r'\bcarro\b', text, re.IGNORECASE):
#                 filters['vehicle_type'] = 'carro'
#             elif re.search(r'\bmoto\b', text, re.IGNORECASE):
#                 filters['vehicle_type'] = 'moto'

#         # 8. Se destination for "Carro"/"Moto", move para vehicle_type
#         if filters.get('destination') and filters['destination'].lower() in ['carro', 'moto']:
#             filters['vehicle_type'] = filters['destination'].lower()
#             filters['destination'] = None

#         # 9. Remove valores vazios (mantém None para padronização)
#         filters = {k: v for k, v in filters.items() if v not in [None, 'null', '']}
#         logger.info(f"Filtros extraídos (final): {filters}")
#         return filters

    def extract_filters(self, text: str) -> dict:
        import re
        filters = {
            "origin": None,
            "destination": None,
            "price_min": None,
            "price_max": None,
            "vehicle_type": None,
            "start_time_after": None,
        }

        # 1. Função para limpar localidades (remove artigos, preposições, verbos)
        def clean_location(loc):
            if not loc:
                return None
            stopwords = ['quero', 'viajar', 'de', 'do', 'da', 'o', 'a', 'para', 'até',
                        'amanhã', 'hoje', 'às', 'horas', 'em', 'no', 'na']
            pattern = r'\b(' + '|'.join(stopwords) + r')\b'
            cleaned = re.sub(pattern, '', loc, flags=re.IGNORECASE).strip()
            cleaned = re.sub(r'\s+', ' ', cleaned).strip()
            return cleaned if cleaned else None

        # 2. Extrai origem com regex (prioridade)
        origin_match = re.search(r'(?:de\s+|do\s+|da\s+)?([A-Za-zÀ-ÖØ-öø-ÿ\s]+?)\s+para\s+', text, re.IGNORECASE)
        if origin_match:
            origem = origin_match.group(1).strip()
            origem = clean_location(origem)
            if origem:
                filters['origin'] = ' '.join(word.capitalize() for word in origem.split())

        # 3. Extrai destino com regex (prioridade)
        dest_match = re.search(r'para\s+([A-Za-zÀ-ÖØ-öø-ÿ\s]+?)(?:\s+até|\s+amanhã|\s+às|\s*$)', text, re.IGNORECASE)
        if dest_match:
            destino = dest_match.group(1).strip()
            destino = clean_location(destino)
            if destino:
                filters['destination'] = ' '.join(word.capitalize() for word in destino.split())

        # 4. Extrai price_max com regex (prioridade)
        price_match = re.search(r'até\s*(\d+[,.]?\d*)', text, re.IGNORECASE)
        if not price_match:
            price_match = re.search(r'(?:R?\$?)\s*(\d+[,.]?\d*)\s*(?:reais)?', text, re.IGNORECASE)
        if price_match:
            filters['price_max'] = float(price_match.group(1).replace(',', '.'))

        # 5. Extrai price_min (se mencionado)
        price_min_match = re.search(r'de\s*(\d+[,.]?\d*)\s*(?:reais)?', text, re.IGNORECASE)
        if price_min_match:
            filters['price_min'] = float(price_min_match.group(1).replace(',', '.'))

        # 6. Extrai vehicle_type com regex (prioridade)
        if re.search(r'\bcarro\b', text, re.IGNORECASE):
            filters['vehicle_type'] = 'carro'
        elif re.search(r'\bmoto\b', text, re.IGNORECASE):
            filters['vehicle_type'] = 'moto'

        # 7. Se origin ou destination não foram capturados, tenta a IA como fallback
        if not filters.get('origin') or not filters.get('destination'):
            prompt = f"""
            Extraia apenas os campos 'origin' e 'destination' do texto, se não forem óbvios.
            Não invente valores. Se não houver, retorne null.
            Texto: "{text}"
            Retorne APENAS o JSON com os campos "origin" e "destination".
            """
            try:
                raw = self.provider.chat(prompt)
                if "```" in raw:
                    start = raw.find("{")
                    end = raw.rfind("}")
                    if start != -1 and end != -1:
                        raw = raw[start:end+1]
                ai_filters = json.loads(raw)
                if not filters.get('origin') and ai_filters.get('origin'):
                    filters['origin'] = ai_filters['origin']
                if not filters.get('destination') and ai_filters.get('destination'):
                    filters['destination'] = ai_filters['destination']
            except Exception as e:
                logger.error(f"Erro ao extrair origin/destination com IA: {e}")

        # 8. Se destination for "Carro"/"Moto", move para vehicle_type (já tratado)
        if filters.get('destination') and filters['destination'].lower() in ['carro', 'moto']:
            filters['vehicle_type'] = filters['destination'].lower()
            filters['destination'] = None

        # 9. Remove campos vazios
        filters = {k: v for k, v in filters.items() if v not in [None, 'null', '']}
        logger.info(f"Filtros extraídos (final): {filters}")
        return filters


        