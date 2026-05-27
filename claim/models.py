from django.db import models

from places.models import Place


class ServiceOffering(models.Model):
    """A service that a claimed Place offers."""

    place = models.ForeignKey(
        Place,
        verbose_name='Negocio',
        on_delete=models.CASCADE,
        related_name='services',
    )
    name = models.CharField('Nombre', max_length=120)
    description = models.TextField('Descripción', blank=True)
    price = models.DecimalField(
        'Precio (ARS)',
        max_digits=10, decimal_places=2,
        null=True, blank=True,
    )
    duration_minutes = models.PositiveIntegerField('Duración (minutos)', default=30)
    is_active = models.BooleanField('Activo', default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Servicio'
        verbose_name_plural = 'Servicios'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.place.name})'
