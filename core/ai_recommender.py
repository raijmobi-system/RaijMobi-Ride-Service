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