from django.contrib import admin

from .models import Place


@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'category', 'address', 'rating',
        'reviews_count', 'source', 'is_active', 'owner',
    )
    list_filter = ('category', 'source', 'is_active')
    search_fields = ('name', 'address', 'google_place_id', 'phone')
    readonly_fields = (
        'google_place_id', 'created_at', 'updated_at', 'last_ingested_at',
    )
    list_select_related = ('owner',)
    autocomplete_fields = ('owner',)
    list_per_page = 50
    fieldsets = (
        ('Identidad', {
            'fields': ('name', 'google_place_id', 'category', 'is_active'),
        }),
        ('Contacto y ubicación', {
            'fields': ('address', 'phone', 'lat', 'lng'),
        }),
        ('Reputación', {
            'fields': ('rating', 'reviews_count', 'hours'),
        }),
        ('Origen', {
            'fields': ('source', 'owner'),
        }),
        ('Metadatos', {
            'fields': ('created_at', 'updated_at', 'last_ingested_at'),
        }),
    )
