from rest_framework.viewsets import ModelViewSet
from ..models import Reservation,Ride,Vehicle,Rating,UserClient
from .serializers import ReservationSerializer,RideSerializer,VehicleSerializer, RatingSerializer, UserClientSerializer

class ReservationViewset(ModelViewSet):
    queryset = Reservation.objects.all()
    serializer_class = ReservationSerializer

class RideViewset(ModelViewSet):
    queryset = Ride.objects.all()
    serializer_class = RideSerializer

class VehicleViewset(ModelViewSet):
    queryset = Vehicle.objects.all()
    serializer_class = VehicleSerializer

class RatingViewset(ModelViewSet):

    queryset = Rating.objects.all()
    serializer_class = RatingSerializer


class UserClientViewset(ModelViewSet):
    queryset = UserClient.objects.all()
    serializer_class = UserClientSerializer

    