from prometheus_client import Counter,Histogram

rides_total = Counter(
    "rides_total",
    "Total de caronas criadas"
)

reservations_total = Counter(
    "reservations_total",
    "Total de reservas criadas"
)

cancelations_total = Counter(
    "cancelations_total",
    "Total de cancelamentos"
)

ai_requests_total = Counter(
    "ai_requests_total",
    "Total de chamadas realizadas para a IA"
)

ai_requests_failed_total = Counter(
    "ai_requests_failed_total",
    "Total de chamadas para IA que falharam"
)

ai_recommendations_total = Counter(
    "ai_recommendations_total",
    "Total de recomendações geradas pela IA"
)

ai_filters_total = Counter(
    "ai_filters_total",
    "Total de filtros inteligentes realizados"
)

ai_response_time_seconds = Histogram(
    "ai_response_time_seconds",
    "Tempo de resposta da IA"
)