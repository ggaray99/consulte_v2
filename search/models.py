from django.db import models


class SearchQuery(models.Model):
    """Registro de cada búsqueda con input: qué pidió el usuario, qué
    entendió el extractor y cuántos resultados devolvimos. Es la base de
    las métricas del MVP (demanda real, calidad del intent, huecos de oferta).
    """

    query = models.CharField('consulta', max_length=300, blank=True)
    engine = models.CharField('motor de intent', max_length=20, blank=True)

    category = models.CharField('categoría detectada', max_length=40, blank=True)
    zone = models.CharField('zona detectada', max_length=80, blank=True)
    urgency = models.CharField('urgencia', max_length=10, blank=True)
    ranking = models.CharField('ranking pedido', max_length=20, blank=True)
    budget = models.CharField('presupuesto', max_length=10, blank=True)

    sort = models.CharField('orden aplicado', max_length=20, blank=True)
    results_count = models.PositiveIntegerField('resultados', default=0)
    has_coords = models.BooleanField('con geolocalización', default=False)
    is_htmx = models.BooleanField('vía HTMX', default=False)

    created_at = models.DateTimeField('fecha', auto_now_add=True)

    class Meta:
        verbose_name = 'búsqueda'
        verbose_name_plural = 'búsquedas'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['category']),
        ]

    def __str__(self):
        return f'{self.query or "(solo filtros)"} → {self.results_count} resultados'
