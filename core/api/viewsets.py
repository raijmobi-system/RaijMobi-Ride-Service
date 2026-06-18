from rest_framework.viewsets import ModelViewSet
from ..models import Reservation,Ride,Vehicle,Rating,UserClient
from .serializers import ReservationSerializer,RideSerializer,VehicleSerializer, RatingSerializer, UserClientSerializer
from .filters import RideFilter   # ajuste o import conforme sua estrutura
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

class ReservationViewset(ModelViewSet):
    queryset = Reservation.objects.all()
    serializer_class = ReservationSerializer

# class RideViewset(ModelViewSet):
#     queryset = Ride.objects.all()
#     serializer_class = RideSerializer

class VehicleViewset(ModelViewSet):
    queryset = Vehicle.objects.all()
    serializer_class = VehicleSerializer

class RatingViewset(ModelViewSet):

    queryset = Rating.objects.all()
    serializer_class = RatingSerializer

    def perform_create(self, serializer):
        
        user = UserClient.objects.get(
            id=self.request.data.get("evaluator")
        )

        serializer.save(
            created_by=user,
            updated_by=user
        )


class UserClientViewset(ModelViewSet):
    queryset = UserClient.objects.all()
    serializer_class = UserClientSerializer

class RideViewset(ModelViewSet):
    queryset = Ride.objects.all()
    serializer_class = RideSerializer
    filterset_class = RideFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['origin', 'destination', 'vehicle__model']   # campos onde fará busca textual
    ordering_fields = ['price', 'start_time', 'available_seats']   # campos permitidos para ordenar
    ordering = ['start_time']                                      # ordenação padrão (opcional)