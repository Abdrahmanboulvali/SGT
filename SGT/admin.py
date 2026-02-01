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

from django.contrib import admin
from .models import PaymentOption, CompanyContact

@admin.register(PaymentOption)
class PaymentOptionAdmin(admin.ModelAdmin):
    list_display = ("label", "code", "phone_number", "is_active", "order")
    list_editable = ("phone_number", "is_active", "order")
    search_fields = ("label", "code", "phone_number")
    ordering = ("order", "label")


@admin.register(CompanyContact)
class CompanyContactAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):

        return not CompanyContact.objects.filter(pk=1).exists()
