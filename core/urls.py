from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api.viewsets import ReservationViewset, RideViewset, VehicleViewset, RatingViewset

router = DefaultRouter()

router.register(r'reservations', ReservationViewset, basename='reservation')
router.register(r'rides', RideViewset, basename='ride')
router.register(r'vehicles', VehicleViewset, basename='vehicle')
router.register(r'ratings', RatingViewset, basename='rating')

urlpatterns = [
    path('', include(router.urls)),
]