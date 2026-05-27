from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('', include('search.urls')),
    path('places/', include('places.urls')),
    path('', include('claim.urls')),
    path('admin/', admin.site.urls),
]
