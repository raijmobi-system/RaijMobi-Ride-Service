from rest_framework.viewsets import ModelViewSet
from ..models import Reservation,Ride,Vehicle,Rating,UserClient
from .serializers import ReservationSerializer,RideSerializer,VehicleSerializer, RatingSerializer, UserClientSerializer
from .permissions import IsDriver

class ReservationViewset(ModelViewSet):
    
    permission_classes = [IsDriver]
    
    queryset = Reservation.objects.all()
    serializer_class = ReservationSerializer

class RideViewset(ModelViewSet):

    permission_classes = [IsDriver]
    
    queryset = Ride.objects.all()
    serializer_class = RideSerializer

class VehicleViewset(ModelViewSet):

    permission_classes = [IsDriver]

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

    