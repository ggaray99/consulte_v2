import math

from django.shortcuts import render

from places.models import Place

from .intent import _normalize, extract_intent

CATEGORY_LABELS = dict(Place.Category.choices)
EARTH_RADIUS_KM = 6371.0


def search(request):
    query = (request.GET.get('q') or '').strip()
    user_lat, user_lng = _parse_coords(request)

    intent = None
    results = []
    sorted_by_distance = False

    if query:
        intent = extract_intent(query)
        results = _query_places(intent, user_lat, user_lng)
        sorted_by_distance = user_lat is not None and user_lng is not None

    context = {
        'query': query,
        'intent': intent,
        'intent_category_label': (
            CATEGORY_LABELS.get(intent['category']) if intent else None
        ),
        'results': results,
        'results_count': len(results),
        'sorted_by_distance': sorted_by_distance,
        'has_coords': user_lat is not None and user_lng is not None,
    }

    if request.headers.get('HX-Request'):
        return render(request, 'search/_results.html', context)
    return render(request, 'search/index.html', context)


def _parse_coords(request):
    try:
        lat = float(request.GET.get('lat', ''))
        lng = float(request.GET.get('lng', ''))
    except (TypeError, ValueError):
        return None, None
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return None, None
    return lat, lng


def _query_places(intent, user_lat, user_lng):
    qs = Place.objects.filter(is_active=True)

    category = intent.get('category')
    if category and category != Place.Category.OTHER.value:
        qs = qs.filter(category=category)

    qs = qs.order_by('-rating', '-reviews_count', 'name')
    results = list(qs[:50])

    # SQLite icontains is accent-sensitive, so filter by zone in Python with
    # the same accent-stripping normalizer the intent extractor uses. If the
    # zone filter eliminates everything, drop it — Google often returns
    # formatted addresses without the neighborhood name.
    zone = intent.get('zone')
    if zone:
        zoned = [p for p in results if zone in _normalize(p.address or '')]
        if zoned:
            results = zoned

    # When the user gave us coordinates, sort by Haversine distance —
    # places with no lat/lng go to the bottom.
    if user_lat is not None and user_lng is not None:
        for p in results:
            p.distance_km = _haversine(user_lat, user_lng, p.lat, p.lng)
        results.sort(key=lambda p: (p.distance_km is None, p.distance_km or 0))

    return results[:30]


def _haversine(lat1, lng1, lat2, lng2):
    if lat2 is None or lng2 is None:
        return None
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))
