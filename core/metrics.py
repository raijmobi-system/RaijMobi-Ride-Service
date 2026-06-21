from prometheus_client import Counter

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