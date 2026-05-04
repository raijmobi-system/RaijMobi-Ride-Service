from django.urls import path,include
from rest_framework.routers import SimpleRouter
from .views import VeiculoViewSet,CaronaViewSet,ReservaViewSet

router = SimpleRouter()
router.register(r'veiculos',VeiculoViewSet)
router.register(r'caronas',CaronaViewSet)
router.register(r'reservas',ReservaViewSet)

urlpatterns = [
    path('',include(router.urls))
]
