from django.contrib import admin
from .models import Vehicule, Chauffeur, Trajet, Voyage, Reservation, User

admin.site.register(Vehicule)
admin.site.register(Chauffeur)
admin.site.register(Trajet)
admin.site.register(Voyage)
admin.site.register(Reservation)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'telephone', 'role', 'is_active')
    list_filter = ('role', 'is_active')
    search_fields = ('username', 'email', 'telephone')