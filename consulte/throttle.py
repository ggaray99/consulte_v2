"""
Rate limiting simple por IP, basado en cache (fixed window).

Suficiente para el MVP: protege el costo de la Claude API y el envío de
emails vía Resend contra loops/abuso. No es exacto bajo concurrencia alta,
pero no necesita infra extra (usa el cache default de Django).
"""

from django.core.cache import cache


def client_ip(request):
    """IP del cliente, respetando X-Forwarded-For (Railway corre detrás de proxy)."""
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', 'unknown')


def allow(request, scope, *, limit, window_seconds):
    """True si el request entra dentro del límite para (scope, IP)."""
    key = f'throttle:{scope}:{client_ip(request)}'
    cache.add(key, 0, window_seconds)
    try:
        count = cache.incr(key)
    except ValueError:
        # La key expiró entre add() e incr(); arrancamos ventana nueva.
        cache.set(key, 1, window_seconds)
        count = 1
    return count <= limit
