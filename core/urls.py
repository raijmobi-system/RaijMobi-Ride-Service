from django.contrib import admin
from django.urls import path,include
from rest_framework.routers import SimpleRouter
from .api.viewsets import ReservationViewset,RideViewset,VehicleViewset
router = SimpleRouter()

router.register(r'reservations', ReservationViewset, basename='reservation')
router.register(r'rides', RideViewset, basename='ride')
router.register(r'vehicles', VehicleViewset, basename='vehicle')

urlpatterns = [
    path('', include(router.urls)),
]
