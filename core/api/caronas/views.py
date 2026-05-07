from rest_framework import viewsets
from .models import Veiculo, Carona,Reserva
from rest_framework.viewsets import ModelViewSet
from .models import Veiculo,Carona,Reserva
from django_filters.rest_framework import DjangoFilterBackend
from .serializers import VeiculoSerializer,CaronaSerializer,ReservaSerializer

class VeiculoViewSet(viewsets.ModelViewSet):
    queryset = Veiculo.objects.all()
    serializer_class = VeiculoSerializer

class CaronaViewSet(viewsets.ModelViewSet):
    queryset = Carona.objects.all()
    serializer_class = CaronaSerializer

    filter_backends = [DjangoFilterBackend]

    filterset_fields = {
        'origem':['icontains'],
        'destino':['icontains'],
        'preco':['gte','lte'],
        'genero':['exact'],
        'data_hora_saida':['gte','lte'],
    }

class ReservaViewSet(viewsets.ModelViewSet):
    queryset = Reserva.objects.all()
    serializer_class  = ReservaSerializer