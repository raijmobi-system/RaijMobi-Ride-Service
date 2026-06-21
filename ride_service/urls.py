from django.contrib import admin
from django.urls import path,include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/ride/', include('core.urls')),
    path("",include("django_prometheus.urls")),
]
