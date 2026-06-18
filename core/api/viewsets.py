from rest_framework.viewsets import ModelViewSet
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from ..models import UserClient, Vehicle, Ride, Reservation, Rating
from .serializers import UserClientSerializer, VehicleSerializer, RideSerializer, ReservationSerializer, RatingSerializer
from .filters import RideFilter

class UserClientViewset(ModelViewSet):
    queryset = UserClient.objects.all()
    serializer_class = UserClientSerializer

class VehicleViewset(ModelViewSet):
    queryset = Vehicle.objects.all()
    serializer_class = VehicleSerializer

class RideViewset(ModelViewSet):
    queryset = Ride.objects.all()
    serializer_class = RideSerializer
    filterset_class = RideFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["origin", "destination", "vehicle__model"]
    ordering_fields = ["price", "start_time", "available_seats"]
    ordering = ["start_time"]

class ReservationViewset(ModelViewSet):
    queryset = Reservation.objects.all()
    serializer_class = ReservationSerializer

class RatingViewset(ModelViewSet):
    queryset = Rating.objects.all()
    serializer_class = RatingSerializer

    def perform_create(self, serializer):
        user = UserClient.objects.get(id=self.request.data.get("evaluator"))
        serializer.save(created_by=user, updated_by=user)