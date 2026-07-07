# core/filters.py
import django_filters
from ..models import Ride
from django.db.models import Q

class RideFilter(django_filters.FilterSet):
    origin_city = django_filters.CharFilter(field_name='origin__city', lookup_expr='icontains')      
    destination_city = django_filters.CharFilter(field_name='destination__city', lookup_expr='icontains')

    origin_state = django_filters.CharFilter(field_name='origin__state', lookup_expr='iexact')
    destination_state = django_filters.CharFilter(field_name='destination__state', lookup_expr='iexact')

    origin = django_filters.CharFilter(method='filter_origin')
    destination = django_filters.CharFilter(method='filter_destination')

    status = django_filters.ChoiceFilter(choices=Ride.STATUS_CHOICES)
    driver = django_filters.UUIDFilter(field_name='vehicle__user__id')

    price_min = django_filters.NumberFilter(field_name='price', lookup_expr='gte')
    price_max = django_filters.NumberFilter(field_name='price', lookup_expr='lte')
    available_seats_min = django_filters.NumberFilter(field_name='available_seats', lookup_expr='gte')
    available_seats_max = django_filters.NumberFilter(field_name='available_seats', lookup_expr='lte')

    start_time_after = django_filters.DateTimeFilter(field_name='start_time', lookup_expr='gte')
    start_time_before = django_filters.DateTimeFilter(field_name='start_time', lookup_expr='lte')

    vehicle_type = django_filters.CharFilter(field_name='vehicle__type_vehicle')
    vehicle_model = django_filters.CharFilter(field_name='vehicle__model', lookup_expr='icontains')
    vehicle_seats_min = django_filters.NumberFilter(field_name='vehicle__seats', lookup_expr='gte')

    class Meta:
        model = Ride
        fields = [
            'origin', 'destination', 'origin_city', 'destination_city', 
            'origin_state', 'destination_state', 'status', 'price', 
            'available_seats', 'start_time'
        ]

    def filter_origin(self, queryset, name, value):
        return queryset.filter(
            Q(origin__city__icontains=value) | 
            Q(origin__state__iexact=value) |
            Q(origin__description__icontains=value)
        )  

    def filter_destination(self, queryset, name, value):
        return queryset.filter(
            Q(destination__city__icontains=value) | 
            Q(destination__state__iexact=value) |
            Q(destination__description__icontains=value)
        )  

    