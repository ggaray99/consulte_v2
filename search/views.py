from django.shortcuts import render

from places.models import Place

from .intent import _normalize, extract_intent

CATEGORY_LABELS = dict(Place.Category.choices)


def search(request):
    query = (request.GET.get('q') or '').strip()
    intent = None
    results = []

    if query:
        intent = extract_intent(query)
        results = _query_places(intent)

    context = {
        'query': query,
        'intent': intent,
        'intent_category_label': (
            CATEGORY_LABELS.get(intent['category']) if intent else None
        ),
        'results': results,
        'results_count': len(results),
    }

    if request.headers.get('HX-Request'):
        return render(request, 'search/_results.html', context)
    return render(request, 'search/index.html', context)


def _query_places(intent):
    qs = Place.objects.filter(is_active=True)

    category = intent.get('category')
    if category and category != Place.Category.OTHER.value:
        qs = qs.filter(category=category)

    qs = qs.order_by('-rating', '-reviews_count', 'name')
    results = list(qs[:30])

    # SQLite icontains is accent-sensitive, so filter by zone in Python with
    # the same accent-stripping normalizer the intent extractor uses. Cheap
    # while the result set is small; revisit when we move to Postgres.
    # If the zone filter eliminates everything, drop it — Google often
    # returns formatted addresses without the neighborhood name (e.g.
    # "C1425 Cdad. Autónoma de Buenos Aires" instead of "Palermo"), so a
    # strict filter would hide otherwise-relevant places.
    zone = intent.get('zone')
    if zone:
        zoned = [p for p in results if zone in _normalize(p.address or '')]
        if zoned:
            results = zoned

    return results
