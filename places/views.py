from django.shortcuts import render

from .models import Place


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
