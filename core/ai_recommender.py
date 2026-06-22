import json
import time
import logging
from abc import ABC, abstractmethod
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from django.core.cache import cache

from .models import Ride, Reservation, UserClient

logger = logging.getLogger(__name__)

# -------------------------------------------------------------------
# 1. Interface comum para qualquer provedor de IA
# -------------------------------------------------------------------
class AIProvider(ABC):
    @abstractmethod
    def chat(self, prompt: str) -> list[dict]:
        """Envia o prompt e retorna uma lista de recomendações (índice, motivo)."""
        ...


# -------------------------------------------------------------------
# 2. Implementações dos provedores (todas no mesmo arquivo)
# -------------------------------------------------------------------
class OpenAIProvider(AIProvider):
    def __init__(self):
        try:
            import openai
            self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        except ImportError:
            raise ImportError("Instale a biblioteca openai: pip install openai")
        self.model = getattr(settings, 'OPENAI_MODEL', 'gpt-4o-mini')

    def chat(self, prompt):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500,
        )
        return self._parse_json(response.choices[0].message.content)

    @staticmethod
    def _parse_json(text):
        return json.loads(text.strip())


class AnthropicProvider(AIProvider):
    def __init__(self):
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        except ImportError:
            raise ImportError("Instale a biblioteca anthropic: pip install anthropic")
        self.model = getattr(settings, 'ANTHROPIC_MODEL', 'claude-3-haiku-20240307')

    def chat(self, prompt):
        message = self.client.messages.create(
            model=self.model,
            max_tokens=500,
            temperature=0.3,
            system="Responda apenas com um array JSON puro, sem nenhum texto adicional.",
            messages=[{"role": "user", "content": prompt}],
        )
        content = message.content[0].text
        return self._parse_json(content)

    @staticmethod
    def _parse_json(text):
        # Claude pode envolver JSON em ```json ... ```
        if text.startswith("```"):
            parts = text.split("```")
            for p in parts:
                p = p.strip()
                if p.startswith("json"):
                    p = p[4:]
                try:
                    return json.loads(p)
                except:
                    continue
        return json.loads(text)


class GeminiProvider(AIProvider):
    def __init__(self):
        try:
            import google.generativeai as genai
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self.model = genai.GenerativeModel(
                getattr(settings, 'GEMINI_MODEL', 'gemini-1.5-flash-latest')
            )
        except ImportError:
            raise ImportError("Instale a biblioteca google-generativeai")
        self.generation_config = genai.types.GenerationConfig(temperature=0.3)

    def chat(self, prompt):
        full_prompt = f"{prompt}\n\nResponda exclusivamente com um array JSON."
        response = self.model.generate_content(
            full_prompt,
            generation_config=self.generation_config
        )
        text = response.text
        return self._parse_json(text)

    @staticmethod
    def _parse_json(text):
        # Gemini pode retornar ```json ...
        if "```" in text:
            start = text.find("[")
            end = text.rfind("]")
            if start != -1 and end != -1:
                text = text[start:end+1]
        return json.loads(text)


class DeepSeekProvider(AIProvider):
    def __init__(self):
        try:
            from openai import OpenAI
            self.client = OpenAI(
                api_key=settings.DEEPSEEK_API_KEY,
                base_url="https://api.deepseek.com/v1"
            )
        except ImportError:
            raise ImportError("Instale a biblioteca openai: pip install openai")
        self.model = getattr(settings, 'DEEPSEEK_MODEL', 'deepseek-chat')

    def chat(self, prompt):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500,
        )
        return json.loads(response.choices[0].message.content.strip())


class GroqProvider(AIProvider):
    def __init__(self):
        try:
            from groq import Groq
            self.client = Groq(api_key=settings.GROQ_API_KEY)
        except ImportError:
            raise ImportError("Instale a biblioteca groq: pip install groq")
        self.model = getattr(settings, 'GROQ_MODEL', 'llama3-8b-8192')

    def chat(self, prompt):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500,
        )
        return json.loads(response.choices[0].message.content.strip())


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
        # Ollama pode retornar ```json ...
        return self._parse_json(text)

    @staticmethod
    def _parse_json(text):
        if "```" in text:
            start = text.find("[")
            end = text.rfind("]")
            if start != -1 and end != -1:
                text = text[start:end+1]
        return json.loads(text)


# -------------------------------------------------------------------
# 3. Fábrica de provedores
# -------------------------------------------------------------------
PROVIDERS = {
    'openai': OpenAIProvider,
    'anthropic': AnthropicProvider,
    'gemini': GeminiProvider,
    'deepseek': DeepSeekProvider,
    'groq': GroqProvider,
    'ollama': OllamaProvider,
}

def get_ai_provider() -> AIProvider:
    name = getattr(settings, 'AI_PROVIDER', 'openai').lower()
    if name not in PROVIDERS:
        raise ValueError(f"Provedor de IA desconhecido: {name}. Opções: {list(PROVIDERS.keys())}")
    return PROVIDERS[name]()


# -------------------------------------------------------------------
# 4. Recomendador com cache simples e fallback
# -------------------------------------------------------------------
class AIRideRecommender:
    def __init__(self):
        self.provider = get_ai_provider()
        self._cache = {}   # cache em memória simples (dict) com TTL

    def recommend(self, user_id, top_n=5, history_limit=10):
        """Retorna lista de dicts com 'ride', 'reason', 'score' (score=0 para IA)."""
        # -- Cache check --
        now = time.time()
        cache_key = str(user_id)
        cached = self._cache.get(cache_key)
        if cached and (now - cached['timestamp']) < 300:  # 5 minutos
            return cached['data']

        # -- Coleta de dados --
        recent_reservations = Reservation.objects.filter(
            passenger_id=user_id,
            status__in=['confirmada', 'finalizada'],
            created_at__gte=timezone.now() - timedelta(days=90)
        ).select_related('ride__vehicle__user').order_by('-created_at')[:history_limit]

        if not recent_reservations:
            # Sem histórico = fallback para caronas ordenadas por preço
            return self._fallback_sort(user_id, top_n)

        # Histórico formatado
        history_text = "Histórico recente de viagens:\n"
        for i, res in enumerate(recent_reservations, 1):
            r = res.ride
            history_text += (
                f"{i}. {r.origin} → {r.destination}, "
                f"Partida: {r.start_time.strftime('%d/%m/%Y %H:%M')}, "
                f"Preço: R$ {r.price}, Vagas pedidas: {res.requested_seats}, "
                f"Motorista: {r.vehicle.user.name} (nota {r.vehicle.user.average_rating})\n"
            )

        # Caronas ativas
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

        # -- Prompt --
        prompt = f"""
Você é um assistente de recomendações para um aplicativo de caronas.
O usuário tem o seguinte histórico:

{history_text}

Com base nesse histórico, selecione as {top_n} melhores caronas disponíveis para ele.
Lista de caronas ativas:

{rides_text}

Escolha as que mais combinam com as preferências do usuário (rotas habituais, faixa de preço, horários, avaliação do motorista).
Responda **exclusivamente** com um array JSON no formato:
[
  {{ "index": "<índice da lista>", "reason": "breve justificativa (máx. 100 caracteres)" }}
]
Sem nenhum texto adicional.
"""

        # -- Chamada à IA --
        try:
            recommendations = self.provider.chat(prompt)
        except Exception as e:
            logger.error(f"Erro ao chamar IA ({type(self.provider).__name__}): {e}")
            return self._fallback_sort(user_id, top_n)

        # -- Mapeamento para objetos Ride --
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
                        "score": 0  # IA não gera score numérico
                    })

        # Se veio vazio, fallback
        if not result:
            return self._fallback_sort(user_id, top_n)

        # -- Armazena em cache local --
        self._cache[cache_key] = {
            'timestamp': now,
            'data': result[:top_n]
        }
        return result[:top_n]

    def _fallback_sort(self, user_id, top_n):
        """Ordena por preço e avaliação do motorista (fallback)."""
        active = Ride.objects.filter(
            status__in=['pendente', 'confirmada'],
            start_time__gte=timezone.now()
        ).select_related('vehicle__user').order_by('price', '-vehicle__user__average_rating')[:top_n]

        return [
            {
                "ride": ride,
                "reason": "Recomendação automática (melhor preço e avaliação)",
                "score": 0
            }
            for ride in active
        ]