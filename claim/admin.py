from django.contrib import admin

from .models import ServiceOffering


@admin.register(ServiceOffering)
class ServiceOfferingAdmin(admin.ModelAdmin):
    list_display = ('name', 'place', 'price', 'duration_minutes', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'place__name')
    autocomplete_fields = ('place',)
    list_select_related = ('place',)
