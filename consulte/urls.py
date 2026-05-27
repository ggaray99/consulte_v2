from django.contrib import admin
from django.http import HttpResponse
from django.urls import path


def placeholder_home(request):
    return HttpResponse(
        '<h1 style="font-family:sans-serif">consulte.</h1>'
        '<p>Marketplace v2 scaffold. Next step: create the first app.</p>',
        content_type='text/html; charset=utf-8',
    )


urlpatterns = [
    path('', placeholder_home, name='home'),
    path('admin/', admin.site.urls),
]
