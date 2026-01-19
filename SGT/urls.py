from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # Vehicules
    path('vehicules/', views.liste_vehicules, name='liste_vehicules'),
    path('vehicules/ajouter/', views.ajouter_vehicule, name='ajouter_vehicule'),
    path('vehicules/modifier/<int:id_vehicule>/', views.modifier_vehicule, name='modifier_vehicule'),
    path('vehicules/supprimer/<int:id_vehicule>/', views.supprimer_vehicule, name='supprimer_vehicule'),

    # Chauffeurs
    path('chauffeurs/', views.liste_chauffeurs, name='liste_chauffeurs'),
    path('chauffeurs/ajouter/', views.ajouter_chauffeur, name='ajouter_chauffeur'),
    path('chauffeurs/modifier/<int:id_chauffeur>/', views.modifier_chauffeur, name='modifier_chauffeur'),
    path('chauffeurs/supprimer/<int:id_chauffeur>/', views.supprimer_chauffeur, name='supprimer_chauffeur'),

    # Trajets
    path('trajets/', views.liste_trajets, name='liste_trajets'),
    path('trajets/ajouter/', views.ajouter_trajet, name='ajouter_trajet'),
    path('trajets/modifier/<int:id_trajet>/', views.modifier_trajet, name='modifier_trajet'),
    path('trajets/supprimer/<int:id_trajet>/', views.supprimer_trajet, name='supprimer_trajet'),

    # ✅ API Trajet (الجديد)
    path('api/trajets/<int:id_trajet>/', views.api_trajet_info, name='api_trajet_info'),

    # ✅ API Trajet (القديم لتفادي 404 وحل مشكلة السعر التلقائي)
    path('api/trajet/<int:id_trajet>/', views.api_trajet_info, name='api_trajet_info_legacy'),

    # Voyages
    path('voyages/', views.liste_voyages, name='liste_voyages'),
    path('voyages/ajouter/', views.ajouter_voyage, name='ajouter_voyage'),
    path('voyages/modifier/<int:id_voyage>/', views.modifier_voyage, name='modifier_voyage'),
    path('voyages/supprimer/<int:id_voyage>/', views.supprimer_voyage, name='supprimer_voyage'),

    # API Voyage Price
    path('api/voyages/<int:id_voyage>/price/', views.api_get_voyage_price, name='api_get_voyage_price'),

    # Clients
    path('clients/', views.liste_clients, name='liste_clients'),
    path('clients/ajouter/', views.ajouter_client, name='ajouter_client'),
    path('clients/modifier/<int:id>/', views.modifier_client, name='modifier_client'),
    path('clients/supprimer/<int:id>/', views.supprimer_client, name='supprimer_client'),

    # Reservations
    path('reservations/', views.liste_reservations, name='liste_reservations'),
    path('reservations/mes-reservations/', views.mes_reservations, name='mes_reservations'),
    path('reservations/ajouter/', views.ajouter_reservation, name='ajouter_reservation'),
    path('reservations/modifier/<int:id_reservation>/', views.modifier_reservation, name='modifier_reservation'),
    path('reservations/supprimer/<int:id_reservation>/', views.supprimer_reservation, name='supprimer_reservation'),
    path('reservations/ticket/<int:id_reservation>/', views.ticket_reservation, name='ticket_reservation'),
    path('reservations/confirmer/<int:id_reservation>/', views.confirmer_paiement, name='confirmer_paiement'),

    # Superviseur / Gestion comptes
    path('gestion-comptes/', views.gestion_comptes, name='gestion_comptes'),
    path('compte/activer/<int:user_id>/', views.activer_compte, name='activer_compte'),
    path('compte/desactiver/<int:user_id>/', views.desactiver_compte, name='desactiver_compte'),
    path('compte/supprimer/<int:user_id>/', views.supprimer_compte, name='supprimer_compte'),
    path('gestion-comptes/changer-role/<int:user_id>/<str:new_role>/', views.changer_role, name='changer_role'),

    # API Mobile
    path('api/mobile/login/', views.api_login_mobile, name='api_login_mobile'),
    path('api/mobile/voyages/', views.api_get_voyages_mobile, name='api_get_voyages_mobile'),
    path('api/mobile/mes-reservations/<int:user_id>/', views.api_mes_reservations_mobile, name='api_mes_reservations_mobile'),
    path('api/mobile/reservations/', views.api_ajouter_reservation_mobile, name='api_ajouter_reservation_mobile'),
    path("api/mobile/ticket/<int:id_reservation>/", views.api_mobile_ticket_pdf, name="api_mobile_ticket_pdf"),
    path("api/mobile/register/", views.api_register_mobile, name="api_register_mobile"),
    path("api/mobile/voyages/", views.mobile_voyages, name="mobile_voyages"),



]
