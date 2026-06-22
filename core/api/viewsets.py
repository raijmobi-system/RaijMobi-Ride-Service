from rest_framework.viewsets import ModelViewSet
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from ..models import UserClient, Vehicle, Ride, Reservation, Rating
from .serializers import UserClientSerializer, VehicleSerializer, RideSerializer, ReservationSerializer, RatingSerializer
from .filters import RideFilter
from ..ai_recommender import AIRideRecommender
from rest_framework.decorators import action
from rest_framework.response import Response

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

    @action(detail=False, methods=['get'], url_path='ai-recommendations')
    def ai_recommendations(self, request):
        user_id = request.query_params.get('user_id')
        if not user_id:
            return Response({'error': 'user_id é obrigatório'}, status=400)
        try:
            user = UserClient.objects.get(id=user_id)
        except UserClient.DoesNotExist:
            return Response({'error': 'Usuário não encontrado'}, status=404)

        top_n = int(request.query_params.get('top_n', 5))
        recommender = AIRideRecommender()
        results = recommender.recommend(user_id, top_n)

        # Serializa as caronas
        rides = [item['ride'] for item in results]
        reasons = [item['reason'] for item in results]
        serializer = RideSerializer(rides, many=True, context={'request': request})
        data = serializer.data
        for i, item in enumerate(data):
            item['ai_reason'] = reasons[i] if i < len(reasons) else ""
        return Response(data)

class ReservationViewset(ModelViewSet):
    queryset = Reservation.objects.all()
    serializer_class = ReservationSerializer

class RatingViewset(ModelViewSet):
    queryset = Rating.objects.all()
    serializer_class = RatingSerializer

    def perform_create(self, serializer):
        user = UserClient.objects.get(id=self.request.data.get("evaluator"))
        serializer.save(created_by=user, updated_by=user)