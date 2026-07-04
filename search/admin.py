from django.contrib import admin

from .models import SearchQuery


@admin.register(SearchQuery)
class SearchQueryAdmin(admin.ModelAdmin):
    list_display = (
        'created_at', 'query', 'engine', 'category', 'zone',
        'sort', 'results_count', 'has_coords',
    )
    list_filter = ('engine', 'category', 'urgency', 'budget', 'has_coords')
    search_fields = ('query', 'zone')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
