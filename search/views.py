import logging
import math
import re

from django.db.models import Prefetch
from django.shortcuts import render

from claim.models import ServiceOffering
from consulte import throttle
from places.models import Place

from .intent import _normalize, extract_intent
from .models import SearchQuery

logger = logging.getLogger(__name__)

CATEGORY_LABELS = dict(Place.Category.choices)
EARTH_RADIUS_KM = 6371.0

# Tope de llamadas a Claude por IP: pasado el límite la búsqueda sigue
# funcionando con el extractor fallback (y con intents ya cacheados).
LLM_THROTTLE_LIMIT = 20
LLM_THROTTLE_WINDOW = 60  # segundos

SORT_CHOICES = [
    ('recommended', 'Recomendados'),
    ('nearby', 'Más cerca'),
    ('best', 'Mejor puntuados'),
    ('worst', 'Peor puntuados'),
    ('popular', 'Más reseñas'),
]
VALID_SORTS = {value for value, _ in SORT_CHOICES}
STOPWORDS = {
    'a', 'al', 'con', 'de', 'del', 'el', 'en', 'es', 'la', 'las', 'lo', 'los',
    'mi', 'por', 'para', 'que', 'quiero', 'un', 'una', 'unos', 'unas', 'y',
    'turno', 'turnos', 'servicio', 'servicios', 'necesito', 'busco', 'cerca',
    'barato', 'barata', 'mejor', 'mejores', 'hoy', 'ya', 'urgente', 'zona',
}

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
        if query:
            use_llm = throttle.allow(
                request, 'search-llm',
                limit=LLM_THROTTLE_LIMIT, window_seconds=LLM_THROTTLE_WINDOW,
            )
            intent = extract_intent(query, use_llm=use_llm)
        sort = _resolve_sort(sort, intent, user_lat, user_lng)
        results = _query_places(intent, user_lat, user_lng, sort=sort, filters=filters, query=query)
        sorted_by_distance = sort == 'nearby' and user_lat is not None and user_lng is not None
        _log_search(request, query=query, intent=intent, sort=sort, results=results,
                    has_coords=user_lat is not None and user_lng is not None)

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


def _log_search(request, *, query, intent, sort, results, has_coords):
    """Registrar la búsqueda para métricas. Nunca debe romper la respuesta."""
    try:
        SearchQuery.objects.create(
            query=query[:300],
            engine=(intent or {}).get('engine', ''),
            category=(intent or {}).get('category') or '',
            zone=(intent or {}).get('zone') or '',
            urgency=(intent or {}).get('urgency') or '',
            ranking=(intent or {}).get('ranking') or '',
            budget=(intent or {}).get('budget') or '',
            sort=sort,
            results_count=len(results),
            has_coords=has_coords,
            is_htmx=bool(request.headers.get('HX-Request')),
        )
    except Exception:
        logger.exception('No se pudo registrar la búsqueda')


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


def _resolve_sort(sort, intent, user_lat, user_lng):
    if not intent:
        return sort

    hint = intent.get('ranking') or 'recommended'
    if sort == 'recommended' and hint in VALID_SORTS:
        if hint != 'nearby' or (user_lat is not None and user_lng is not None):
            return hint
    return sort


def _query_places(intent, user_lat, user_lng, *, sort, filters, query):
    qs = Place.objects.filter(is_active=True).prefetch_related(
        Prefetch(
            'services',
            queryset=ServiceOffering.objects.filter(is_active=True).order_by('name'),
        )
    )

    # Category: explicit filter wins over Claude's extraction.
    category = filters['category'] or (intent.get('category') if intent else None)
    if category and category != Place.Category.OTHER.value:
        qs = qs.filter(category=category)

    if filters['min_rating'] is not None:
        qs = qs.filter(rating__gte=filters['min_rating'])

    if filters['min_reviews'] is not None:
        qs = qs.filter(reviews_count__gte=filters['min_reviews'])

    if sort in ('best', 'worst'):
        qs = qs.filter(
            reviews_count__gte=MIN_REVIEWS_FOR_REPUTATION_SORT,
            rating__isnull=False,
        )

    if sort == 'popular':
        qs = qs.order_by('-reviews_count', '-rating', 'name')
    else:
        qs = qs.order_by('-rating', '-reviews_count', 'name')

    results = list(qs[:200])

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

    tokens = _search_tokens(query, intent)
    budget = (intent or {}).get('budget', 'any')
    for p in results:
        p.distance_km = getattr(p, 'distance_km', None)
        _decorate_place_match(p, tokens=tokens, intent=intent, budget=budget)

    if sort == 'nearby':
        results.sort(
            key=lambda p: (
                p.distance_km is None,
                round(p.distance_km or 0, 4),
                -p.search_score,
                -(p.rating or 0),
                -p.reviews_count,
                p.name.lower(),
            )
        )
    elif sort == 'best':
        results.sort(
            key=lambda p: (
                -p.has_match,
                -p.search_score,
                -(p.rating or 0),
                -p.reviews_count,
                p.name.lower(),
            )
        )
    elif sort == 'worst':
        results.sort(
            key=lambda p: (
                -p.has_match,
                -p.search_score,
                p.rating if p.rating is not None else 999,
                -p.reviews_count,
                p.name.lower(),
            )
        )
    elif sort == 'popular':
        results.sort(
            key=lambda p: (
                -p.has_match,
                -p.search_score,
                -p.reviews_count,
                -(p.rating or 0),
                p.name.lower(),
            )
        )
    else:
        results.sort(
            key=lambda p: (
                -p.search_score,
                -(p.rating or 0),
                -p.reviews_count,
                p.distance_km if p.distance_km is not None else 999999,
                p.name.lower(),
            )
        )

    return results[:30]


def _search_tokens(query, intent):
    base = (intent or {}).get('raw_service') or query or ''
    norm = _normalize(base)

    zone = (intent or {}).get('zone')
    if zone:
        norm = norm.replace(zone, ' ')

    tokens = []
    for token in re.findall(r'[a-z0-9]+', norm):
        if len(token) < 3 or token in STOPWORDS:
            continue
        tokens.append(token)
    return tokens


def _decorate_place_match(place, *, tokens, intent, budget):
    place_text = _normalize(
        ' '.join(filter(None, [
            place.name,
            place.address,
            place.get_category_display(),
        ]))
    )
    raw_service = _normalize((intent or {}).get('raw_service') or '')
    category = (intent or {}).get('category')

    service_matches = []
    service_prices = []
    service_score = 0
    for service in place.services.all():
        text = _normalize(' '.join(filter(None, [service.name, service.description])))
        hits = sum(1 for token in tokens if token in text)
        phrase_hit = 1 if raw_service and len(raw_service) >= 4 and raw_service in text else 0
        score = hits * 5 + phrase_hit * 8
        if score <= 0:
            continue
        service_matches.append((score, service))
        service_score += score
        if service.price is not None:
            service_prices.append(float(service.price))

    text_hits = sum(1 for token in tokens if token in place_text)
    place_phrase_hit = 1 if raw_service and len(raw_service) >= 4 and raw_service in place_text else 0
    category_bonus = 4 if category and category != Place.Category.OTHER.value and place.category == category else 0
    claimed_bonus = 3 if place.owner_id else 0
    rating_bonus = (place.rating or 0) * 1.5 + math.log1p(place.reviews_count or 0)
    budget_bonus = _budget_bonus(service_prices, budget)

    top_services = [service for _, service in sorted(service_matches, key=lambda item: (-item[0], item[1].name.lower()))[:2]]
    place.matched_services = top_services
    place.match_reason = top_services[0].name if top_services else ''
    place.search_score = (
        service_score
        + text_hits * 3
        + place_phrase_hit * 5
        + category_bonus
        + claimed_bonus
        + rating_bonus
        + budget_bonus
    )
    place.has_match = 1 if (service_matches or text_hits or place_phrase_hit or category_bonus) else 0


def _budget_bonus(prices, budget):
    if not prices or budget == 'any':
        return 0

    min_price = min(prices)
    max_price = max(prices)
    if budget == 'cheap':
        return max(0, 200000 - min_price) / 10000
    if budget == 'premium':
        return max_price / 10000
    return 0


def _haversine(lat1, lng1, lat2, lng2):
    if lat2 is None or lng2 is None:
        return None
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))
