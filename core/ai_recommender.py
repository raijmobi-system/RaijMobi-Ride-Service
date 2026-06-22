import json
import time
import logging
from abc import ABC, abstractmethod

from django.conf import settings
from django.utils import timezone

from .models import Ride, Reservation

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# 1. Interface e provedor (apenas Ollama)
# -------------------------------------------------------------------
class AIProvider(ABC):
    @abstractmethod
    def chat(self, prompt: str) -> list[dict]:
        """Envia o prompt e retorna uma lista de recomendações (índice, motivo)."""
        ...


class OllamaProvider(AIProvider):
    def __init__(self):
        try:
            import requests
            self.requests = requests
        except ImportError:
            raise ImportError("Instale a biblioteca requests")
        self.base_url = getattr(settings, 'OLLAMA_URL', 'http://localhost:11434')
        self.model = getattr(settings, 'OLLAMA_MODEL', 'llama3')

    def chat(self, prompt):
        resp = self.requests.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False
            }
        )
        data = resp.json()
        text = data["message"]["content"]
        # Limpa possíveis marcações JSON
        return self._parse_json(text)

    @staticmethod
    def _parse_json(text):
        if "```" in text:
            start = text.find("[")
            end = text.rfind("]")
            if start != -1 and end != -1:
                text = text[start:end+1]
        return json.loads(text)


def get_ai_provider() -> AIProvider:
    return OllamaProvider()


# -------------------------------------------------------------------
# 2. Recomendador APENAS com IA (sem fallback)
# -------------------------------------------------------------------
class AIRideRecommender:
    def __init__(self):
        self.provider = get_ai_provider()
        self._cache = {}   # cache em memória simples (dict) com TTL

    def recommend(self, user_id, top_n=5, history_limit=10):
        """
        Retorna lista de dicts com 'ride', 'reason', 'score' (score=0 para IA).
        SEMPRE usa a IA, independente de histórico. Se a IA falhar, retorna lista vazia.
        """
        now = time.time()
        cache_key = str(user_id)
        cached = self._cache.get(cache_key)
        if cached and (now - cached['timestamp']) < 300:  # 5 minutos
            return cached['data']

        # -- Coleta de dados --
        recent_reservations = Reservation.objects.filter(
            passenger_id=user_id,
            status__in=['confirmada', 'finalizada'],
            created_at__gte=timezone.now() - timezone.timedelta(days=90)
        ).select_related('ride__vehicle__user').order_by('-created_at')[:history_limit]

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
            status__in=['pendente', 'confirmada'],
            start_time__gte=timezone.now()
        ).select_related('vehicle__user').order_by('start_time')

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

        try:
            recommendations = self.provider.chat(prompt)
        except Exception as e:
            logger.error(f"Erro ao chamar IA ({type(self.provider).__name__}): {e}")
            return []

        result = []
        for rec in recommendations:
            idx = str(rec.get("index"))
            reason = rec.get("reason", "")
            if idx in ride_map:
                ride = Ride.objects.filter(id=ride_map[idx]).first()
                if ride:
                    result.append({
                        "ride": ride,
                        "reason": reason,
                        "score": 0
                    })

        if not result:
            logger.warning("IA retornou nenhuma recomendação válida.")
            return []

        self._cache[cache_key] = {
            'timestamp': now,
            'data': result[:top_n]
        }
        return result[:top_n]

# core/ai_recommender.py (adicionar no final)
class AIFilterExtractor:
    def __init__(self):
        self.provider = get_ai_provider()

    def extract_filters(self, text: str) -> dict:
        import re
        filters = {}

        # 1. Tenta extrair com IA
        prompt = f"""
Você é um assistente que extrai critérios de busca de caronas a partir de um texto em português.
O texto do usuário é: "{text}"

Extraia APENAS os campos explicitamente mencionados. Não invente valores.
Campos possíveis:
- "origin": local de partida
- "destination": local de destino
- "price_max": preço máximo (número)
- "vehicle_type": "carro" ou "moto"
- "start_time_after": só se mencionar dia/horário

Exemplo: para "Terminal Central para Shopping até 40" a saída deve ser:
{{ "origin": "Terminal Central", "destination": "Shopping", "price_max": 40 }}

Retorne APENAS o JSON.
"""
        try:
            raw = self.provider.chat(prompt)
            logger.info(f"Resposta bruta da IA (filtro): {raw[:200]}...")
            # Limpa possíveis marcações
            if "```" in raw:
                start = raw.find("{")
                end = raw.rfind("}")
                if start != -1 and end != -1:
                    raw = raw[start:end+1]
            filters = json.loads(raw)
        except Exception as e:
            logger.error(f"Erro ao extrair filtros com IA: {e}")
            filters = {}

        # 2. Fallback com regex (sempre aplicado para complementar)
        # Extrai origem: "de X para Y" ou "X para Y"
        origin_match = re.search(r'(?:de\s+)?([^,para]+?)\s+para\s+', text, re.IGNORECASE)
        if origin_match:
            filters['origin'] = origin_match.group(1).strip()
        # Extrai destino: após "para"
        dest_match = re.search(r'para\s+([^,]+?)(?:\s+até|\s*$)', text, re.IGNORECASE)
        if dest_match:
            filters['destination'] = dest_match.group(1).strip()
        # Extrai preço: "até 40" ou "R$ 40"
        price_match = re.search(r'(?:até|R?\$?)\s*(\d+[,.]?\d*)', text, re.IGNORECASE)
        if price_match:
            filters['price_max'] = float(price_match.group(1).replace(',', '.'))
        # Extrai tipo de veículo
        if re.search(r'\bcarro\b', text, re.IGNORECASE):
            filters['vehicle_type'] = 'carro'
        elif re.search(r'\bmoto\b', text, re.IGNORECASE):
            filters['vehicle_type'] = 'moto'

        # 3. Normalização e limpeza
        if 'origin' in filters:
            filters['origin'] = filters['origin'].strip().title()
        if 'destination' in filters:
            dest = filters['destination'].strip().title()
            # Se destination for "Carro" ou "Moto", mover para vehicle_type
            if dest.lower() in ['Carro', 'Moto']:
                filters['vehicle_type'] = dest.lower()
                del filters['destination']
            else:
                filters['destination'] = dest
        if 'vehicle_type' in filters:
            filters['vehicle_type'] = filters['vehicle_type'].lower()

        # Remove campos vazios ou None
        filters = {k: v for k, v in filters.items() if v not in [None, 'null', '']}
        logger.info(f"Filtros extraídos: {filters}")
        return filters