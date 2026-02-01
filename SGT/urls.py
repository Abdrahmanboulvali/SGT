from django.urls import path
from . import views

urlpatterns = [
    # ============ Auth (Web) ============
    path("register/", views.register_view, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),

    # ============ Dashboard ============
    path("", views.dashboard, name="dashboard"),

    # ============ Vehicules ============
    path("vehicules/", views.liste_vehicules, name="liste_vehicules"),
    path("vehicules/add/", views.ajouter_vehicule, name="ajouter_vehicule"),
    path("vehicules/<int:id_vehicule>/edit/", views.modifier_vehicule, name="modifier_vehicule"),
    path("vehicules/<int:id_vehicule>/delete/", views.supprimer_vehicule, name="supprimer_vehicule"),

    # ============ Chauffeurs ============
    path("chauffeurs/", views.liste_chauffeurs, name="liste_chauffeurs"),
    path("chauffeurs/add/", views.ajouter_chauffeur, name="ajouter_chauffeur"),
    path("chauffeurs/<int:id_chauffeur>/edit/", views.modifier_chauffeur, name="modifier_chauffeur"),
    path("chauffeurs/<int:id_chauffeur>/delete/", views.supprimer_chauffeur, name="supprimer_chauffeur"),

    # ============ Trajets ============
    path("trajets/", views.liste_trajets, name="liste_trajets"),
    path("trajets/add/", views.ajouter_trajet, name="ajouter_trajet"),
    path("trajets/<int:id_trajet>/edit/", views.modifier_trajet, name="modifier_trajet"),
    path("trajets/<int:id_trajet>/delete/", views.supprimer_trajet, name="supprimer_trajet"),

    # API trajet info
    path("api/trajets/<int:id_trajet>/info/", views.api_trajet_info, name="api_trajet_info"),

    # ============ Voyages ============
    path("voyages/", views.liste_voyages, name="liste_voyages"),
    path("voyages/add/", views.ajouter_voyage, name="ajouter_voyage"),
    path("voyages/<int:id_voyage>/edit/", views.modifier_voyage, name="modifier_voyage"),
    path("voyages/<int:id_voyage>/delete/", views.supprimer_voyage, name="supprimer_voyage"),

    # API voyage price
    path("api/voyage-price/<int:id_voyage>/", views.api_get_voyage_price, name="api_voyage_price"),

    # ============ Clients ============
    path("clients/", views.liste_clients, name="liste_clients"),
    path("clients/add/", views.ajouter_client, name="ajouter_client"),
    path("clients/<int:id>/edit/", views.modifier_client, name="modifier_client"),
    path("clients/<int:id>/delete/", views.supprimer_client, name="supprimer_client"),

    # ============ Reservations (Web) ============
    path("reservations/", views.liste_reservations, name="liste_reservations"),
    path("reservations/me/", views.mes_reservations, name="mes_reservations"),
    path("reservations/add/", views.ajouter_reservation, name="ajouter_reservation"),
    path("reservations/<int:id_reservation>/edit/", views.modifier_reservation, name="modifier_reservation"),
    path("reservations/<int:id_reservation>/delete/", views.supprimer_reservation, name="supprimer_reservation"),
    path("reservations/<int:id_reservation>/ticket/", views.ticket_reservation, name="ticket_reservation"),
    path("reservations/<int:id_reservation>/confirm-payment/", views.confirmer_paiement, name="confirmer_paiement"),

    # ============ Superviseur ============
    path("superviseur/comptes/", views.gestion_comptes, name="gestion_comptes"),
    path("superviseur/comptes/<int:user_id>/activer/", views.activer_compte, name="activer_compte"),
    path("superviseur/comptes/<int:user_id>/desactiver/", views.desactiver_compte, name="desactiver_compte"),
    path("superviseur/comptes/<int:user_id>/supprimer/", views.supprimer_compte, name="supprimer_compte"),
    path("superviseur/comptes/<int:user_id>/role/<str:new_role>/", views.changer_role, name="changer_role"),

    # ============ Mobile APIs ============
    path("api/mobile/login/", views.api_login_mobile, name="api_login_mobile"),
    path("api/mobile/register/", views.api_register_mobile, name="api_register_mobile"),
    path("api/mobile/voyages/", views.api_get_voyages_mobile, name="api_get_voyages_mobile"),


    path("api/mobile/reservations/", views.api_ajouter_reservation_mobile, name="api_mobile_reservations"),


    path("api/mobile/reservations/create/", views.api_ajouter_reservation_mobile, name="api_mobile_reservations_create"),


    path("api/mobile/mes-reservations/<int:user_id>/", views.api_mes_reservations_mobile, name="api_mes_reservations_mobile"),


    path("api/mobile/reservations/<int:user_id>/", views.api_mes_reservations_mobile, name="api_mobile_reservations_by_user"),

    # PDF Ticket Mobile
    path("api/mobile/ticket/<int:id_reservation>/", views.api_mobile_ticket_pdf, name="api_mobile_ticket_pdf"),

    path("api/web/clients/search/", views.api_web_clients_search, name="api_web_clients_search"),
    path("api/mobile/payment-options/", views.api_mobile_payment_options, name="api_mobile_payment_options"),
]
