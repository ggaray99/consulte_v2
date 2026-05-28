from django.conf import settings
from django.db import models


class Place(models.Model):
    """A business indexed from Google Places or claimed by an owner."""

    class Source(models.TextChoices):
        GOOGLE = 'google', 'Google Places'
        CLAIMED = 'claimed', 'Reclamado'

    class Category(models.TextChoices):
        DENTIST = 'dentist', 'Dentista'
        HAIR_CARE = 'hair_care', 'Peluquería'
        BEAUTY_SALON = 'beauty_salon', 'Salón de belleza'
        DOCTOR = 'doctor', 'Médico'
        PHYSIOTHERAPIST = 'physiotherapist', 'Kinesiólogo'
        VETERINARY_CARE = 'veterinary_care', 'Veterinaria'
        SPA = 'spa', 'Spa'
        OTHER = 'other', 'Otro'

    google_place_id = models.CharField(
        'Google place_id', max_length=255, unique=True
    )
    name = models.CharField('Nombre', max_length=255)
    address = models.CharField('Dirección', max_length=500, blank=True)
    phone = models.CharField('Teléfono', max_length=50, blank=True)
    lat = models.FloatField('Latitud', null=True, blank=True)
    lng = models.FloatField('Longitud', null=True, blank=True)

    category = models.CharField(
        'Categoría',
        max_length=32,
        choices=Category.choices,
        default=Category.OTHER,
    )
    rating = models.FloatField('Rating', null=True, blank=True)
    reviews_count = models.PositiveIntegerField('Cantidad de reviews', default=0)
    hours = models.JSONField('Horarios', default=dict, blank=True)
    photos = models.JSONField(
        'Fotos (Google photo_references)', default=list, blank=True
    )
    website = models.URLField('Web', max_length=500, blank=True)

    source = models.CharField(
        'Origen',
        max_length=16,
        choices=Source.choices,
        default=Source.GOOGLE,
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='Dueño',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='places',
    )
    is_active = models.BooleanField('Activo', default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_ingested_at = models.DateTimeField(
        'Última ingesta', null=True, blank=True
    )

    class Meta:
        verbose_name = 'Negocio'
        verbose_name_plural = 'Negocios'
        ordering = ['-rating', 'name']
        indexes = [
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['lat', 'lng']),
        ]

    def __str__(self):
        return self.name

    @property
    def is_claimed(self):
        return self.source == self.Source.CLAIMED and self.owner_id is not None
