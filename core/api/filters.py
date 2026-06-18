# core/filters.py
import django_filters
from ..models import Ride

class RideFilter(django_filters.FilterSet):
    # Filtros exatos
    origin = django_filters.CharFilter(lookup_expr='icontains')      # busca parcial (case insensitive)
    destination = django_filters.CharFilter(lookup_expr='icontains')
    status = django_filters.ChoiceFilter(choices=Ride.STATUS_CHOICES)

    # Filtros por intervalo numérico
    price_min = django_filters.NumberFilter(field_name='price', lookup_expr='gte')
    price_max = django_filters.NumberFilter(field_name='price', lookup_expr='lte')
    available_seats_min = django_filters.NumberFilter(field_name='available_seats', lookup_expr='gte')
    available_seats_max = django_filters.NumberFilter(field_name='available_seats', lookup_expr='lte')

    # Filtro por data/hora de partida (a partir de)
    start_time_after = django_filters.DateTimeFilter(field_name='start_time', lookup_expr='gte')
    start_time_before = django_filters.DateTimeFilter(field_name='start_time', lookup_expr='lte')

    # Filtros relacionados ao veículo
    vehicle_type = django_filters.CharFilter(field_name='vehicle__type_vehicle')
    vehicle_model = django_filters.CharFilter(field_name='vehicle__model', lookup_expr='icontains')
    vehicle_seats_min = django_filters.NumberFilter(field_name='vehicle__seats', lookup_expr='gte')

    class Meta:
        model = Ride
        fields = [
            'origin',
            'destination',
            'status',
            'price',
            'available_seats',
            'start_time',
            'vehicle__type_vehicle',
            'vehicle__model',
        ]