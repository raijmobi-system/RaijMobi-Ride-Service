# ride_service/views.py
from rest_framework.viewsets import ModelViewSet
from rest_framework.views import APIView
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status,permissions
from django_filters.rest_framework import DjangoFilterBackend
from django.db import models
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.core.cache import cache
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from ..kafka_producer import send_ride_event

import requests

from ..models import UserClient, Vehicle, Ride, Reservation, Rating
from .serializers import UserClientSerializer, VehicleSerializer, RideSerializer, ReservationSerializer, RatingSerializer
from .filters import RideFilter
from ..ai_recommender import AIRideRecommender, AIFilterExtractor
from ..services.stripe_service import StripePaymentService

from easyaudit.models import CRUDEvent
from django.db.models import Q

class UserClientViewset(ModelViewSet):
    queryset = UserClient.objects.all()
    serializer_class = UserClientSerializer


class VehicleViewset(ModelViewSet):
    queryset = Vehicle.objects.all()
    serializer_class = VehicleSerializer
    paginate_by = 10
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        return Vehicle.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class RideViewset(ModelViewSet):
    queryset = Ride.objects.all()
    serializer_class = RideSerializer
    filterset_class = RideFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["origin", "destination", "vehicle__model"]
    ordering_fields = ["price", "start_time", "available_seats"]
    ordering = ["start_time"]

    @action(detail=False, methods=['get'], url_path='admin-logs', permission_classes=[IsAuthenticated])
    def admin_logs(self, request):
        """
        GET /api/ride/admin-logs/
        Retorna o histórico completo do django-easy-audit específico deste banco de dados.
        """
        busca = request.query_params.get('busca', '')
        
        # ♻️ Fatiamento [:100] removido para carregar todos os logs existentes
        queryset = CRUDEvent.objects.select_related('user', 'content_type').all().order_by('-datetime')

        if busca:
            queryset = queryset.filter(
                Q(user__username__icontains=busca) | 
                Q(object_repr__icontains=busca) | 
                Q(content_type__model__icontains=busca)
            )

        dados = []
        for log in queryset:
            dados.append({
                "id": str(log.id),
                "user_name": log.user.username if log.user else "Sistema",
                "content_type": log.content_type.name if log.content_type else "Modelo Oculto",
                "object_repr": log.object_repr,
                "event_type": log.event_type,
                "datetime": log.datetime.isoformat()
            })

        return Response(dados)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            print("❌ ERRO DA API (DRF):", serializer.errors)
        return super().create(request, *args, **kwargs)
    
    def perform_create(self, serializer):
        ride = serializer.save()
        send_ride_event(ride)
    
    def perform_update(self, serializer):
        instance = self.get_object()
        old_status = instance.status
        ride = serializer.save()

        if old_status != 'cancelada' and ride.status == 'cancelada':
            reservas_para_estornar = ride.reservations.filter(status='confirmada')
            for reservation in reservas_para_estornar:
                payment_intent_id = getattr(reservation, 'stripe_payment_intent_id', None)
                if payment_intent_id:
                    StripePaymentService.refund_payment(payment_intent_id)
                reservation.status = 'cancelada'
                reservation.save()

    @action(detail=False, methods=['get'], url_path='ai-recommendations')
    def ai_recommendations(self, request):
        # Pega diretamente do usuário logado na requisição (evita depender de query params)
        user = request.user
        if not user or not user.is_authenticated:
            return Response({'error': 'Usuário não autenticado'}, status=401)

        top_n = int(request.query_params.get('top_n', 5))
        recommender = AIRideRecommender()
        
        
        results = recommender.recommend(user.id, top_n)

        rides = [item['ride'] for item in results]
        reasons = [item['reason'] for item in results]
        serializer = RideSerializer(rides, many=True, context={'request': request})
        data = serializer.data
        for i, item in enumerate(data):
            item['ai_reason'] = reasons[i] if i < len(reasons) else ""
        return Response(data)

    @action(detail=False, methods=['post'], url_path='ai-filter')
    def ai_filter(self, request):
        text = request.data.get('text')
        if not text:
            return Response({'error': 'Campo "text" é obrigatório'}, status=status.HTTP_400_BAD_REQUEST)

        extractor = AIFilterExtractor()
        filters_dict = extractor.extract_filters(text)

        if not filters_dict:
            return Response({'error': 'Não foi possível extrair filtros do texto'}, status=status.HTTP_400_BAD_REQUEST)

        def capitalize_words(s):
            return ' '.join(word.capitalize() for word in s.strip().split())

        if 'origin' in filters_dict:
            filters_dict['origin'] = capitalize_words(filters_dict['origin'])
        if 'destination' in filters_dict:
            dest = capitalize_words(filters_dict['destination'])
            if dest.lower() in ['carro', 'moto']:
                filters_dict['vehicle_type'] = dest.lower()
                del filters_dict['destination']
            else:
                filters_dict['destination'] = dest
        if 'vehicle_type' in filters_dict:
            filters_dict['vehicle_type'] = filters_dict['vehicle_type'].lower()
        filters_dict = {k: v for k, v in filters_dict.items() if v not in [None, 'null', '']}

        queryset = self.get_queryset()
        filterset = RideFilter(data=filters_dict, queryset=queryset, request=request)

        if filterset.is_valid():
            filtered_queryset = filterset.qs.order_by('start_time')
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
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['passenger', 'ride', 'status']

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            print("❌ ERRO DE VALIDAÇÃO NA RESERVA:", serializer.errors)
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        # 1. Salva a reserva atrelando ao passageiro logado
        reservation = serializer.save(passenger=self.request.user,status='pendente')
        
        # 2. (Importante) Subtrai as vagas imediatamente ao criar a reserva
        ride = reservation.ride
        ride.available_seats -= reservation.requested_seats
        ride.save()

    def perform_update(self, serializer):
        instance = self.get_object()
        old_status = instance.status
        reservation = serializer.save()

        if old_status != 'cancelada' and reservation.status == 'cancelada':
            ride = reservation.ride
            ride.available_seats += reservation.requested_seats
            ride.save()
            print(f"♻️ {reservation.requested_seats} vaga(s) devolvida(s) para a carona #{ride.id}")

            payment_intent_id = getattr(reservation, 'stripe_payment_intent_id', None)
            if old_status == 'confirmada' and payment_intent_id:
                StripePaymentService.refund_payment(payment_intent_id)
                print(f"💸 Estorno solicitado no Stripe para o pagamento {payment_intent_id}")


class RatingViewset(ModelViewSet):
    queryset = Rating.objects.all()
    serializer_class = RatingSerializer

    def perform_create(self, serializer):
        user = UserClient.objects.get(id=self.request.data.get("evaluator"))
        serializer.save(created_by=user, updated_by=user)


# No topo do seu viewsets.py, certifique-se de importar a Reserva
# from ..models import Reservation

# Dentro do seu viewsets.py:

class CreatePaymentIntentView(APIView):
    def post(self, request):
        reservation_id = request.data.get('reservation_id')
        platform = request.data.get('platform', 'mobile') # 🌟 Captura se é 'web' ou 'mobile'

        if not reservation_id:
            return Response({'error': 'reservation_id é obrigatório'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            reservation = Reservation.objects.get(id=reservation_id)
            ride = reservation.ride
            total_amount = int(ride.price * reservation.requested_seats * 100)

            # === 🌟 SE A REQUISIÇÃO VIER DA WEB ===
            if platform == 'web':
                checkout_url = StripePaymentService.create_checkout_session(
                    amount_cents=total_amount,
                    ride=ride,
                    reservation_id=str(reservation.id)
                )
                return Response({'checkout_url': checkout_url}, status=status.HTTP_200_OK)

            # === SE VIER DO APP MOBILE NATIVO ===
            sheet_params = StripePaymentService.create_payment_sheet_params(
                amount_cents=total_amount,
                user=request.user,
                reservation_id=str(reservation.id)
            )

            return Response(sheet_params, status=status.HTTP_200_OK)
            
        except Reservation.DoesNotExist:
            return Response({'error': 'Reserva não encontrada'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        

@api_view(['GET'])
@permission_classes([AllowAny])
def city_suggestions(request):
    query = request.GET.get('q', '').strip().lower()
    if len(query) < 3:
        return Response([])

    cities = cache.get('ibge_cities_list')
    if not cities:
        try:
            resp = requests.get('https://servicodados.ibge.gov.br/api/v1/localidades/municipios', timeout=5)
            data = resp.json()
            cities = [{'nome': c['nome'], 'estado': c['microrregiao']['mesorregiao']['UF']['sigla']} for c in data]
            cache.set('ibge_cities_list', cities, 86400)
        except Exception:
            return Response([])

    matches = [
        c for c in cities 
        if query in c['nome'].lower()
    ][:3]

    return Response(matches)

class RideAdminLogsView(APIView):
    # Definido como AllowAny temporariamente para bater com o teste inicial do front
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request):
        try:
            busca = request.query_params.get('busca', '').strip()
            
            # Busca todos os eventos de auditoria do Ride Service
            query = CRUDEvent.objects.all().order_by('-datetime')

            if busca:
                query = query.filter(
                    Q(user__username__icontains=busca) |
                    Q(object_repr__icontains=busca) |
                    Q(event_type__icontains=busca)
                )

            logs_formatados = []
            for event in query:
                # Mapeia o tipo de evento numérico para String que o front já entende
                acao_map = {1: 'Create', 2: 'Update', 3: 'Delete'}
                acao_string = acao_map.get(event.event_type, 'Update')

                logs_formatados.append({
                    "id": event.id,
                    "quem_mexeu": event.user.get_full_name() or event.user.username if event.user else "Sistema",
                    "data": event.datetime.strftime('%d/%m/%Y'),
                    "hora": event.datetime.strftime('%H:%M:%S'),
                    "microsservico": "Ride Service",
                    "acao": acao_string,
                    "no_que_mexeu": event.object_repr or "Objeto não identificado"
                })

            return Response(logs_formatados, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"erro": f"Erro interno no Ride Service: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )