# from rest_framework.viewsets import ModelViewSet
# from rest_framework.filters import SearchFilter, OrderingFilter
# from django_filters.rest_framework import DjangoFilterBackend
# from ..models import UserClient, Vehicle, Ride, Reservation, Rating
# from .serializers import UserClientSerializer, VehicleSerializer, RideSerializer, ReservationSerializer, RatingSerializer
# from .filters import RideFilter
# from rest_framework.decorators import action
# from rest_framework.response import Response
# from ..ai_recommender import AIRideRecommender, AIFilterExtractor


# class UserClientViewset(ModelViewSet):
#     queryset = UserClient.objects.all()
#     serializer_class = UserClientSerializer

# class VehicleViewset(ModelViewSet):
#     queryset = Vehicle.objects.all()
#     serializer_class = VehicleSerializer

# class RideViewset(ModelViewSet):
#     queryset = Ride.objects.all()
#     serializer_class = RideSerializer
#     filterset_class = RideFilter
#     filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
#     search_fields = ["origin", "destination", "vehicle__model"]
#     ordering_fields = ["price", "start_time", "available_seats"]
#     ordering = ["start_time"]

#     @action(detail=False, methods=['post'], url_path='ai-filter')
#     def ai_filter(self, request):
#         text = request.data.get('text')
#         if not text:
#             return Response({'error': 'Campo "text" é obrigatório'}, status=400)
#         extractor = AIFilterExtractor()
#         filters_dict = extractor.extract_filters(text)
#         # ... resto do código

#     @action(detail=False, methods=['get'], url_path='ai-recommendations')
#     def ai_recommendations(self, request):
#         user_id = request.query_params.get('user_id')
#         if not user_id:
#             return Response({'error': 'user_id é obrigatório'}, status=400)
#         try:
#             user = UserClient.objects.get(id=user_id)
#         except UserClient.DoesNotExist:
#             return Response({'error': 'Usuário não encontrado'}, status=404)

#         top_n = int(request.query_params.get('top_n', 5))
#         recommender = AIRideRecommender()
#         results = recommender.recommend(user_id, top_n)

#         # Serializa as caronas
#         rides = [item['ride'] for item in results]
#         reasons = [item['reason'] for item in results]
#         serializer = RideSerializer(rides, many=True, context={'request': request})
#         data = serializer.data
#         for i, item in enumerate(data):
#             item['ai_reason'] = reasons[i] if i < len(reasons) else ""
#         return Response(data)

#     @action(detail=False, methods=['post'], url_path='ai-filter')
#     def ai_filter(self, request):
#         """
#         Recebe um texto, extrai filtros via IA e retorna as caronas filtradas.
#         """
#         text = request.data.get('text')
#         if not text:
#             return Response({'error': 'Campo "text" é obrigatório'}, status=status.HTTP_400_BAD_REQUEST)

#         # Extrai filtros com IA
#         extractor = AIFilterExtractor()
#         filters_dict = extractor.extract_filters(text)

#         if not filters_dict:
#             return Response({'error': 'Não foi possível extrair filtros do texto'}, status=status.HTTP_400_BAD_REQUEST)

#         # Aplica os filtros usando o RideFilter
#         queryset = self.get_queryset()
#         filterset = RideFilter(data=filters_dict, queryset=queryset, request=request)
#         if filterset.is_valid():
#             filtered_queryset = filterset.qs
#             # Ordenação padrão (opcional)
#             filtered_queryset = filtered_queryset.order_by('start_time')
#             serializer = self.get_serializer(filtered_queryset, many=True)
#             return Response({
#                 'filters_applied': filters_dict,
#                 'count': filtered_queryset.count(),
#                 'results': serializer.data
#             })
#         else:
#             return Response({
#                 'error': 'Filtros inválidos',
#                 'details': filterset.errors
#             }, status=status.HTTP_400_BAD_REQUEST)

# class ReservationViewset(ModelViewSet):
#     queryset = Reservation.objects.all()
#     serializer_class = ReservationSerializer

# class RatingViewset(ModelViewSet):
#     queryset = Rating.objects.all()
#     serializer_class = RatingSerializer

#     def perform_create(self, serializer):
#         user = UserClient.objects.get(id=self.request.data.get("evaluator"))
#         serializer.save(created_by=user, updated_by=user)


from rest_framework.viewsets import ModelViewSet
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from django_filters.rest_framework import DjangoFilterBackend
from django.db import models

from ..models import UserClient, Vehicle, Ride, Reservation, Rating
from .serializers import UserClientSerializer, VehicleSerializer, RideSerializer, ReservationSerializer, RatingSerializer
from .filters import RideFilter
from ..ai_recommender import AIRideRecommender, AIFilterExtractor


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

        rides = [item['ride'] for item in results]
        reasons = [item['reason'] for item in results]
        serializer = RideSerializer(rides, many=True, context={'request': request})
        data = serializer.data
        for i, item in enumerate(data):
            item['ai_reason'] = reasons[i] if i < len(reasons) else ""
        return Response(data)

    @action(detail=False, methods=['post'], url_path='ai-filter')
    def ai_filter(self, request):
        """
        Recebe um texto, extrai filtros via IA e retorna as caronas filtradas.
        """
        text = request.data.get('text')
        if not text:
            return Response({'error': 'Campo "text" é obrigatório'}, status=status.HTTP_400_BAD_REQUEST)

        extractor = AIFilterExtractor()
        filters_dict = extractor.extract_filters(text)

        if not filters_dict:
            return Response({'error': 'Não foi possível extrair filtros do texto'}, status=status.HTTP_400_BAD_REQUEST)

        # Normalização dos valores
        def capitalize_words(s):
            return ' '.join(word.capitalize() for word in s.strip().split())

        if 'origin' in filters_dict:
            filters_dict['origin'] = capitalize_words(filters_dict['origin'])
        if 'destination' in filters_dict:
            dest = capitalize_words(filters_dict['destination'])
            # Se destination for "Carro" ou "Moto", mover para vehicle_type
            if dest.lower() in ['Carro', 'Moto']:
                filters_dict['vehicle_type'] = dest.lower()
                del filters_dict['destination']
            else:
                filters_dict['destination'] = dest
        if 'vehicle_type' in filters_dict:
            filters_dict['vehicle_type'] = filters_dict['vehicle_type'].lower()
        # Remove campos None ou vazios
        filters_dict = {k: v for k, v in filters_dict.items() if v not in [None, 'null', '']}

        queryset = self.get_queryset()
        filterset = RideFilter(data=filters_dict, queryset=queryset, request=request)

        if filterset.is_valid():
            filtered_queryset = filterset.qs.order_by('start_time')
            # Fallback: se não encontrou nada, tenta apenas com origem, destino e tipo de veículo
            if filtered_queryset.count() == 0:
                fallback_dict = {k: v for k, v in filters_dict.items() if k in ['origin', 'destination', 'vehicle_type']}
                if fallback_dict:
                    fallback_filter = RideFilter(data=fallback_dict, queryset=queryset, request=request)
                    if fallback_filter.is_valid():
                        filtered_queryset = fallback_filter.qs.order_by('start_time')
                        filters_dict = fallback_dict

            serializer = self.get_serializer(filtered_queryset, many=True)
            return Response({
                'filters_applied': filters_dict,
                'count': filtered_queryset.count(),
                'results': serializer.data
            })
        else:
            return Response({
                'error': 'Filtros inválidos',
                'details': filterset.errors
            }, status=status.HTTP_400_BAD_REQUEST)


class ReservationViewset(ModelViewSet):
    queryset = Reservation.objects.all()
    serializer_class = ReservationSerializer


class RatingViewset(ModelViewSet):
    queryset = Rating.objects.all()
    serializer_class = RatingSerializer

    def perform_create(self, serializer):
        user = UserClient.objects.get(id=self.request.data.get("evaluator"))
        serializer.save(created_by=user, updated_by=user)