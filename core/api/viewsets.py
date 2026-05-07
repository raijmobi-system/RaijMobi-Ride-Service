from rest_framework.viewsets import ModelViewSet
from ..models import Reservation,Ride,Vehicle
from .serializers import ReservationSerializer,RideSerializer,VehicleSerializer

class ReservationViewset(ModelViewSet):
    queryset = Reservation.objects.all()
    serializer_class = ReservationSerializer

class RideViewset(ModelViewSet):
    queryset = Ride.objects.all()
    serializer_class = RideSerializer

class VehicleViewset(ModelViewSet):
    queryset = Vehicle.objects.all()
    serializer_class = VehicleSerializer

    