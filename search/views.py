import math

from django.shortcuts import render

from places.models import Place

from .intent import _normalize, extract_intent

CATEGORY_LABELS = dict(Place.Category.choices)
EARTH_RADIUS_KM = 6371.0

SORT_CHOICES = [
    ('recommended', 'Recomendados'),
    ('nearby', 'Más cerca'),
    ('best', 'Mejor puntuados'),
    ('worst', 'Peor puntuados'),
    ('popular', 'Más reseñas'),
]
VALID_SORTS = {value for value, _ in SORT_CHOICES}

# Minimum reviews to be considered for best/worst sort — keeps junk places
# with 1-2 outlier ratings out of the top/bottom.
MIN_REVIEWS_FOR_REPUTATION_SORT = 5


def search(request):
    query = (request.GET.get('q') or '').strip()
    user_lat, user_lng = _parse_coords(request)

    sort = request.GET.get('sort', 'recommended')
    if sort not in VALID_SORTS:
        sort = 'recommended'

    filters = {
        'category': (request.GET.get('category') or '').strip() or None,
        'min_rating': _parse_float(request.GET.get('min_rating')),
        'min_reviews': _parse_int(request.GET.get('min_reviews')),
    }

    has_active_filters = bool(filters['category'] or filters['min_rating'] or filters['min_reviews'])
    has_input = bool(query) or has_active_filters

    intent = None
    results = []
    sorted_by_distance = False

    if has_input:
        intent = extract_intent(query) if query else None
        results = _query_places(intent, user_lat, user_lng, sort=sort, filters=filters)
        sorted_by_distance = sort == 'nearby' and user_lat is not None and user_lng is not None

    context = {
        'query': query,
        'intent': intent,
        'intent_category_label': (
            CATEGORY_LABELS.get(intent['category']) if intent else None
        ),
        'results': results,
        'results_count': len(results),
        'sort': sort,
        'sort_choices': SORT_CHOICES,
        'filters': filters,
        'has_active_filters': has_active_filters,
        'categories': Place.Category.choices,
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


def _parse_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _query_places(intent, user_lat, user_lng, *, sort, filters):
    qs = Place.objects.filter(is_active=True)

    # Category: explicit filter wins over Claude's extraction.
    category = filters['category'] or (intent.get('category') if intent else None)
    if category and category != Place.Category.OTHER.value:
        qs = qs.filter(category=category)

    if filters['min_rating'] is not None:
        qs = qs.filter(rating__gte=filters['min_rating'])

    if filters['min_reviews'] is not None:
        qs = qs.filter(reviews_count__gte=filters['min_reviews'])

    # Apply sort
    if sort == 'best':
        qs = qs.filter(
            reviews_count__gte=MIN_REVIEWS_FOR_REPUTATION_SORT,
            rating__isnull=False,
        ).order_by('-rating', '-reviews_count', 'name')
    elif sort == 'worst':
        qs = qs.filter(
            reviews_count__gte=MIN_REVIEWS_FOR_REPUTATION_SORT,
            rating__isnull=False,
        ).order_by('rating', '-reviews_count', 'name')
    elif sort == 'popular':
        qs = qs.order_by('-reviews_count', '-rating', 'name')
    else:
        # 'recommended' default and 'nearby' (which sorts in Python below)
        qs = qs.order_by('-rating', '-reviews_count', 'name')

    results = list(qs[:50])

    # Zone filter (Python-side, accent-insensitive). If it eliminates
    # everything, drop it — Google often returns formatted addresses
    # without the neighborhood name.
    zone = intent.get('zone') if intent else None
    if zone:
        zoned = [p for p in results if zone in _normalize(p.address or '')]
        if zoned:
            results = zoned

    # Compute distance for every result when coords are present; only
    # re-sort if user explicitly picked "nearby".
    if user_lat is not None and user_lng is not None:
        for p in results:
            p.distance_km = _haversine(user_lat, user_lng, p.lat, p.lng)
        if sort == 'nearby':
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
