from rest_framework import viewsets
from .models import Veiculo, Carona,Reserva
from .serializers import VeiculoSerializer,CaronaSerializer,ReservaSerializer

class VeiculoViewSet(viewsets.ModelViewSet):
    queryset = Veiculo.objects.all()
    serializer_class = VeiculoSerializer

class CaronaViewSet(viewsets.ModelViewSet):
    queryset = Carona.objects.all()
    serializer_class = CaronaSerializer

class ReservaViewSet(viewsets.ModelViewSet):
    queryset = Reserva.objects.all()
    serializer_class  = ReservaSerializer