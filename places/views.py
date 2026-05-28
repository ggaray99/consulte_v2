import requests
from django.conf import settings
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render

from .models import Place

GOOGLE_PHOTO_URL = 'https://maps.googleapis.com/maps/api/place/photo'
GOOGLE_STATICMAP_URL = 'https://maps.googleapis.com/maps/api/staticmap'


def place_detail(request, place_id):
    place = get_object_or_404(Place, pk=place_id, is_active=True)
    services = place.services.filter(is_active=True) if place.owner_id else []
    weekday_hours = (place.hours or {}).get('weekday_text', [])
    photo_count = len(place.photos or [])
    return render(request, 'places/place_detail.html', {
        'place': place,
        'services': services,
        'weekday_hours': weekday_hours,
        'photo_count': photo_count,
        'has_photos': photo_count > 0,
        'has_coords': place.lat is not None and place.lng is not None,
    })


def place_photo(request, place_id, index):
    place = get_object_or_404(Place, pk=place_id, is_active=True)
    photos = place.photos or []
    if index < 0 or index >= len(photos):
        raise Http404
    if not settings.GOOGLE_PLACES_API_KEY:
        raise Http404

    try:
        width = max(200, min(int(request.GET.get('w', 800)), 1600))
    except (TypeError, ValueError):
        width = 800

    upstream = requests.get(
        GOOGLE_PHOTO_URL,
        params={
            'maxwidth': width,
            'photo_reference': photos[index],
            'key': settings.GOOGLE_PLACES_API_KEY,
        },
        timeout=10,
    )
    if upstream.status_code != 200:
        raise Http404

    response = HttpResponse(
        upstream.content,
        content_type=upstream.headers.get('Content-Type', 'image/jpeg'),
    )
    response['Cache-Control'] = 'public, max-age=86400'
    return response


def place_static_map(request, place_id):
    place = get_object_or_404(Place, pk=place_id, is_active=True)
    if place.lat is None or place.lng is None:
        raise Http404
    if not settings.GOOGLE_PLACES_API_KEY:
        raise Http404

    upstream = requests.get(
        GOOGLE_STATICMAP_URL,
        params={
            'center': f'{place.lat},{place.lng}',
            'zoom': '16',
            'size': '800x320',
            'scale': '2',
            'markers': f'color:0x0047AB|{place.lat},{place.lng}',
            'key': settings.GOOGLE_PLACES_API_KEY,
        },
        timeout=10,
    )
    if upstream.status_code != 200:
        raise Http404

    response = HttpResponse(
        upstream.content,
        content_type=upstream.headers.get('Content-Type', 'image/png'),
    )
    response['Cache-Control'] = 'public, max-age=86400'
    return response


def place_list(request):
    """Listado simple de negocios activos. Placeholder visual."""
    qs = Place.objects.filter(is_active=True)

    category = request.GET.get('category', '').strip()
    if category:
        qs = qs.filter(category=category)

    places = list(qs[:200])
    return render(request, 'places/place_list.html', {
        'places': places,
        'total': qs.count(),
        'category_filter': category,
        'categories': Place.Category.choices,
    })
