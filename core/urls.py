from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api.viewsets import ReservationViewset, RideViewset, VehicleViewset, RatingViewset,UserClientViewset
from django.conf import settings
from django.conf.urls.static import static


router = DefaultRouter()

router.register(r'reservations', ReservationViewset, basename='reservation')
router.register(r'rides', RideViewset, basename='ride')
router.register(r'vehicles', VehicleViewset, basename='vehicle')
router.register(r'ratings', RatingViewset, basename='rating')
router.register(r'users', UserClientViewset, basename='users')

urlpatterns = [
    path('', include(router.urls)),

]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,document_root=settings.MEDIA_ROOT)