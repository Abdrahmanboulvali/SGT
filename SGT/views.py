# views.py
from functools import wraps
from django.core.exceptions import PermissionDenied

from .models import User, Chauffeur, Voyage

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, get_user_model, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, FileResponse
from django.db.models import Sum, Q, Count, F, Value, DecimalField, ExpressionWrapper
from django.db.models.functions import TruncDate, Coalesce
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from datetime import timedelta
from PIL import Image
import numpy as np
import easyocr
import re
import json
import io

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors
import qrcode

from .models import Vehicule, Chauffeur, Trajet, Voyage, Reservation
from .forms import (
    VehiculeForm, ChauffeurForm, TrajetForm,
    VoyageForm, ReservationForm, LoginForm, RegisterForm, ClientForm
)

User = get_user_model()


from django.db.models import Func, IntegerField, TextField


class SgtSiegesReserves(Func):
    function = "public.sgt_sieges_reserves"
    output_field = IntegerField()

class SgtSiegesDisponibles(Func):
    function = "public.sgt_sieges_disponibles"
    output_field = IntegerField()

class SgtCheckStatutVoyage(Func):
    function = "public.sgt_check_statut_voyage"
    output_field = TextField()



# =========================
# Helpers (pouvoirs)
# =========================

def is_superviseur(user):

    if user.is_superuser or user.is_staff:
        return True
    return getattr(user, "role", "") in ("SUPERVISEUR", "ADMIN", "STAFF")


def superviseur_required(view_func):
    @login_required
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not is_superviseur(request.user):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return _wrapped


# =========================
# Auth (Web)
# =========================

def register_view(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.role = "CLIENT"
            user.is_active = True
            user.save()
            login(request, user)
            messages.success(request, f"Bienvenue {user.username} !")
            return redirect("dashboard")
    else:
        form = RegisterForm()
    return render(request, "auth/register.html", {"form": form})


def login_view(request):
    if request.method == "POST":
        form = LoginForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()

            # Empêcher le client d'accéder au site web (mais toujours autoriser l'administrateur/le personnel).
            if getattr(user, "role", "") == "CLIENT" and not user.is_staff and not user.is_superuser:
                messages.error(request, "Accès Web interdit pour les clients. Veuillez utiliser l'application mobile.")
                return render(request, "auth/login.html", {"form": form})

            login(request, user)
            return redirect("dashboard")

        messages.error(request, "Login ou mot de passe incorrect.")
    else:
        form = LoginForm()

    return render(request, "auth/login.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("login")


# =========================
# Dashboard (Web)
# =========================

@login_required
def dashboard(request):
    now = timezone.now()
    today = now.date()
    threshold = now + timedelta(minutes=30)
    seven_days_ago = today - timedelta(days=6)
    thirty_days_ago = today - timedelta(days=29)

    stats = {
        "vehicules": Vehicule.objects.count(),
        "chauffeurs": Chauffeur.objects.count(),
        "trajets": Trajet.objects.count(),
        "voyages": Voyage.objects.count(),
        "reservations": Reservation.objects.count(),
        "clients": User.objects.filter(role="CLIENT").count(),
        "reservations_today": Reservation.objects.filter(date_reservation__date=today).count(),
        "voyages_today": Voyage.objects.filter(date_depart=today).count(),
    }

    dec_field = DecimalField(max_digits=18, decimal_places=2)
    revenue_expr = ExpressionWrapper(
        F("nb_sieges") * F("voyage__prix_par_siege"),
        output_field=dec_field
    )

    revenue_today = (
        Reservation.objects
        .filter(date_reservation__date=today)
        .exclude(statut="annulé")
        .aggregate(total=Coalesce(Sum(revenue_expr), Value(0), output_field=dec_field))
        ["total"]
    )

    days_7 = [seven_days_ago + timedelta(days=i) for i in range(7)]
    labels_7d = [d.strftime("%d/%m") for d in days_7]

    qs_res_7d = (
        Reservation.objects
        .filter(date_reservation__date__gte=seven_days_ago)
        .exclude(statut="annulé")
        .annotate(day=TruncDate("date_reservation"))
        .values("day")
        .annotate(count=Count("id_reservation"), rev=Sum(revenue_expr))
    )

    res_dict = {r["day"]: r["count"] for r in qs_res_7d}
    rev_dict = {r["day"]: float(r["rev"]) if r["rev"] else 0.0 for r in qs_res_7d}
    reservations_7d = [res_dict.get(d, 0) for d in days_7]
    revenue_7d = [rev_dict.get(d, 0.0) for d in days_7]

    res_30 = Reservation.objects.filter(date_reservation__date__gte=thirty_days_ago)
    total_30 = res_30.count()
    annule_30 = res_30.filter(statut="annulé").count()
    taux_annulation_30 = (annule_30 / total_30 * 100) if total_30 > 0 else 0

    voyages_7 = Voyage.objects.filter(date_depart__gte=seven_days_ago, date_depart__lte=today)
    total_cap = voyages_7.aggregate(s=Sum("vehicule__capacite"))["s"] or 0
    reserved_seats = (
        Reservation.objects
        .filter(voyage__in=voyages_7)
        .exclude(statut="annulé")
        .aggregate(s=Sum("nb_sieges"))["s"] or 0
    )
    taux_occupation_7 = (reserved_seats / total_cap * 100) if total_cap > 0 else 0

    raw_upcoming = (
        Voyage.objects
        .filter(
            Q(date_depart__gt=threshold.date())
            | Q(date_depart=threshold.date(), heure_depart__gt=threshold.time())
        )
        .order_by("date_depart", "heure_depart")[:5]
    )

    upcoming_voyages = []
    for v in raw_upcoming:
        res_count = (
            Reservation.objects
            .filter(voyage=v)
            .exclude(statut="annulé")
            .aggregate(s=Sum("nb_sieges"))["s"] or 0
        )
        if res_count < v.vehicule.capacite:
            upcoming_voyages.append({
                "trajet": v.trajet,
                "date": v.date_depart,
                "heure": v.heure_depart,
                "remaining": v.vehicule.capacite - res_count,
                "cap": v.vehicule.capacite,
            })

    top_trajets = (
        Reservation.objects
        .filter(date_reservation__date__gte=thirty_days_ago)
        .values("voyage__trajet__ville_depart", "voyage__trajet__ville_arrivee")
        .annotate(nb=Count("id_reservation"))
        .order_by("-nb")[:5]
    )

    context = {
        **stats,
        "revenue_today": revenue_today,
        "revenue_7d": revenue_7d,
        "labels_7d": labels_7d,
        "reservations_7d": reservations_7d,
        "upcoming_voyages": upcoming_voyages,
        "top_trajets": top_trajets,
        "taux_annulation_30": taux_annulation_30,
        "taux_occupation_7": taux_occupation_7,
    }
    return render(request, "dashboard.html", context)


# =========================
# Vehicules (Web)
# =========================

@login_required
def liste_vehicules(request):
    vehicules = Vehicule.objects.all()
    return render(request, "vehicules/liste.html", {"vehicules": vehicules})


@login_required
def ajouter_vehicule(request):
    if request.method == "POST":
        form = VehiculeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Véhicule ajoutée avec succès.")
            return redirect("liste_vehicules")
    else:
        form = VehiculeForm()
    return render(request, "vehicules/form.html", {"form": form})


@login_required
def modifier_vehicule(request, id_vehicule):
    vehicule = get_object_or_404(Vehicule, id_vehicule=id_vehicule)
    if request.method == "POST":
        form = VehiculeForm(request.POST, instance=vehicule)
        if form.is_valid():
            form.save()
            messages.success(request, "Véhicule mise à jour avec succès.")
            return redirect("liste_vehicules")
    else:
        form = VehiculeForm(instance=vehicule)
    return render(request, "vehicules/form.html", {"form": form, "title": "Modifier Véhicule"})


@login_required
def supprimer_vehicule(request, id_vehicule):
    vehicule = get_object_or_404(Vehicule, id_vehicule=id_vehicule)
    vehicule.delete()
    messages.warning(request, "Véhicule supprimée.")
    return redirect("liste_vehicules")


# =========================
# Chauffeurs (Web)
# =========================

@login_required
def liste_chauffeurs(request):
    chauffeurs = Chauffeur.objects.all()
    return render(request, "chauffeurs/liste.html", {"chauffeurs": chauffeurs})


@login_required
def ajouter_chauffeur(request):
    if request.method == "POST":
        form = ChauffeurForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Chauffeur ajouté avec succès.")
            return redirect("liste_chauffeurs")
    else:
        form = ChauffeurForm()
    return render(request, "chauffeurs/form.html", {"form": form})


@login_required
def modifier_chauffeur(request, id_chauffeur):
    chauffeur = get_object_or_404(Chauffeur, id_chauffeur=id_chauffeur)
    if request.method == "POST":
        form = ChauffeurForm(request.POST, instance=chauffeur)
        if form.is_valid():
            form.save()
            messages.success(request, "Chauffeur modifié avec succès.")
            return redirect("liste_chauffeurs")
    else:
        form = ChauffeurForm(instance=chauffeur)
    return render(request, "chauffeurs/form.html", {"form": form, "title": "Modifier Chauffeur"})


@login_required
def supprimer_chauffeur(request, id_chauffeur):
    chauffeur = get_object_or_404(Chauffeur, id_chauffeur=id_chauffeur)
    chauffeur.delete()
    messages.warning(request, "Chauffeur supprimé avec succès.")
    return redirect("liste_chauffeurs")


# =========================
# Trajets (Web + API)
# =========================

@login_required
def liste_trajets(request):
    trajets = Trajet.objects.all()
    return render(request, "trajets/liste.html", {"trajets": trajets})


@login_required
def ajouter_trajet(request):
    if request.method == "POST":
        form = TrajetForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Trajet ajouté avec succès.")
            return redirect("liste_trajets")
    else:
        form = TrajetForm()
    return render(request, "trajets/form.html", {"form": form, "title": "Ajouter Trajet"})


@login_required
def modifier_trajet(request, id_trajet):
    trajet = get_object_or_404(Trajet, id_trajet=id_trajet)
    if request.method == "POST":
        form = TrajetForm(request.POST, instance=trajet)
        if form.is_valid():
            form.save()
            messages.success(request, "Trajet modifié avec succès.")
            return redirect("liste_trajets")
    else:
        form = TrajetForm(instance=trajet)
    return render(request, "trajets/form.html", {"form": form, "title": "Modifier Trajet"})


@login_required
def supprimer_trajet(request, id_trajet):
    trajet = get_object_or_404(Trajet, id_trajet=id_trajet)
    trajet.delete()
    messages.warning(request, "Trajet supprimé.")
    return redirect("liste_trajets")


@csrf_exempt
def api_trajet_info(request, id_trajet):
    t = get_object_or_404(Trajet, id_trajet=id_trajet)

    candidates = ["distance_km", "distance", "km", "distanceKm", "distance_kilometres"]
    dist_val = None
    used_field = None

    for f in candidates:
        if hasattr(t, f):
            v = getattr(t, f)
            if v is not None:
                dist_val = v
                used_field = f
                break

    dist = float(dist_val) if dist_val else 0.0

    return JsonResponse({
        "id": t.id_trajet,
        "depart": t.ville_depart,
        "arrivee": t.ville_arrivee,
        "distance_km": dist,
        "_field_used": used_field,
    })


# =========================
# Voyages (Web + API)
# =========================

@login_required
def liste_voyages(request):
    voyages = (
        Voyage.objects
        .select_related("trajet", "vehicule")
        .annotate(
            seats_left=SgtSiegesDisponibles(F("id_voyage")),
            statut_db=SgtCheckStatutVoyage(F("id_voyage")),
        )
        .order_by("-date_depart", "-heure_depart")
    )

    voyage_data = []
    for v in voyages:
        is_open = (v.statut_db == "OUVERT")

        voyage_data.append({
            "obj": v,
            "seats_left": int(v.seats_left or 0),
            "is_open": is_open,
            "statut": v.statut_db,
        })

    return render(request, "voyages/liste.html", {"voyage_data": voyage_data})


@login_required
def ajouter_voyage(request):
    if request.method == "POST":
        form = VoyageForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Voyage ajouté avec succès.")
            return redirect("liste_voyages")
    else:
        form = VoyageForm()
    return render(request, "voyages/form.html", {"form": form})


@login_required
def modifier_voyage(request, id_voyage):
    voyage = get_object_or_404(Voyage, id_voyage=id_voyage)
    if request.method == "POST":
        form = VoyageForm(request.POST, instance=voyage)
        if form.is_valid():
            form.save()
            messages.success(request, "Voyage modifié avec succès.")
            return redirect("liste_voyages")
    else:
        form = VoyageForm(instance=voyage)
    return render(request, "voyages/form.html", {"form": form, "title": "Modifier Voyage"})


@login_required
def supprimer_voyage(request, id_voyage):
    voyage = get_object_or_404(Voyage, id_voyage=id_voyage)
    voyage.delete()
    messages.warning(request, "Voyage supprimé.")
    return redirect("liste_voyages")




# =========================
# Clients (Web)
# =========================

@login_required
def liste_clients(request):
    clients = User.objects.filter(role="CLIENT")
    return render(request, "clients/liste.html", {"clients": clients})


@login_required
def ajouter_client(request):
    if request.method == "POST":
        form = ClientForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.role = "CLIENT"
            user.is_active = True
            user.save()
            messages.success(request, "Client ajouté avec succès.")
            return redirect("liste_clients")
    else:
        form = ClientForm()
    return render(request, "clients/form.html", {"form": form, "title": "Ajouter Client"})


@login_required
def modifier_client(request, id):
    client = get_object_or_404(User, id=id, role="CLIENT")
    if request.method == "POST":
        form = ClientForm(request.POST, instance=client)
        if form.is_valid():
            form.save()
            messages.success(request, "Client modifié avec succès.")
            return redirect("liste_clients")
    else:
        form = ClientForm(instance=client)
    return render(request, "clients/form.html", {"form": form, "title": "Modifier Client"})


@login_required
def supprimer_client(request, id):
    client = get_object_or_404(User, id=id, role="CLIENT")
    client.delete()
    messages.warning(request, "Client supprimé.")
    return redirect("liste_clients")


# =========================
# Reservations (Web)
# =========================


@login_required
def mes_reservations(request):
    if getattr(request.user, "role", "") != "CLIENT":
        messages.error(request, "Accès non autorisé.")
        return redirect("dashboard")
    reservations = Reservation.objects.filter(client=request.user).order_by("-date_reservation")
    return render(request, "reservations/mes_reservations.html", {"reservations": reservations})



@login_required
def supprimer_reservation(request, id_reservation):
    res = get_object_or_404(Reservation, id_reservation=id_reservation)
    res.delete()
    messages.warning(request, "Réservation supprimée.")
    return redirect("liste_reservations")


@login_required
def ticket_reservation(request, id_reservation):
    """
    ✅ إرسال montant_total للـ template
    بدل الاعتماد على حقل داخل model
    """
    res = get_object_or_404(Reservation, id_reservation=id_reservation)

    montant_total = 0.0
    try:
        montant_total = float(res.nb_sieges * (res.voyage.prix_par_siege or 0))
    except Exception:
        montant_total = 0.0

    return render(request, "reservations/ticket.html", {
        "reservation": res,
        "res": res,
        "montant_total": montant_total,
    })


@login_required
def confirmer_paiement(request, id_reservation):
    res = get_object_or_404(Reservation, id_reservation=id_reservation)
    res.statut_paiement = "paye"
    res.statut = "confirmé"
    res.save()
    messages.success(request, "Paiement confirmé.")
    return redirect("liste_reservations")


# =========================
# Gestion comptes (Superviseur)
# =========================

@superviseur_required
def gestion_comptes(request):
    utilisateurs_en_attente = User.objects.filter(is_active=False).order_by("-date_joined")
    utilisateurs_actifs = User.objects.filter(is_active=True).order_by("-date_joined")

    return render(request, "superviseur/gestion_comptes.html", {
        "utilisateurs_en_attente": utilisateurs_en_attente,
        "utilisateurs_actifs": utilisateurs_actifs,
    })


@superviseur_required
def activer_compte(request, user_id):
    u = get_object_or_404(User, id=user_id)
    u.is_active = True
    u.save()
    messages.success(request, "Compte activé.")
    return redirect("gestion_comptes")


@superviseur_required
def desactiver_compte(request, user_id):
    u = get_object_or_404(User, id=user_id)
    u.is_active = False
    u.save()
    messages.warning(request, "Compte désactivé.")
    return redirect("gestion_comptes")


@superviseur_required
def supprimer_compte(request, user_id):
    u = get_object_or_404(User, id=user_id)
    u.delete()
    messages.warning(request, "Compte supprimé.")
    return redirect("gestion_comptes")


@superviseur_required
def changer_role(request, user_id, new_role):

    allowed_roles = {"CLIENT", "AGENT", "CHAUFFEUR", "SUPERVISEUR", "ADMIN"}

    if new_role not in allowed_roles:
        messages.error(request, "Rôle invalide.")
        return redirect("gestion_comptes")

    u = get_object_or_404(User, id=user_id)


    if u.id == request.user.id:
        messages.error(request, "Impossible de modifier votre propre rôle.")
        return redirect("gestion_comptes")


    if new_role == "CHAUFFEUR":
        Chauffeur.objects.get_or_create(
            user=u,
            defaults={
                "nom": (u.get_full_name().strip() or u.username),
                "telephone": u.telephone,
            },
        )
    else:

        try:
            ch = u.chauffeur_profile
            ch.user = None
            ch.save()
        except Exception:
            pass

    u.role = new_role
    u.save()

    messages.success(request, "Rôle modifié.")
    return redirect("gestion_comptes")



# =========================
# OCR (Vérification du paiement par photo)
# =========================

_reader = None

def get_reader():
    "Chargement du lecteur OCR une seule fois (chargement différé)."
    global _reader
    if _reader is None:
        _reader = easyocr.Reader(['ar', 'en'], gpu=False)
    return _reader


def verify_payment_ocr(image_file, expected_amount, company_phone="37614881"):
    """
    يرجع:
      (ok: bool, transaction_id: str|None)

    ok=True إذا:
      - رقم الشركة موجود
      - المبلغ موجود
      - رقم عملية (transaction_id) موجود
    """
    try:
        if not image_file:
            return False, None

        image_file.seek(0)
        img = Image.open(image_file).convert("RGB")

        # تسريع OCR: تصغير الصورة إذا كانت كبيرة
        img.thumbnail((1400, 1400))

        img_np = np.array(img)
        results = get_reader().readtext(img_np, detail=0)

        full_text = " ".join(results).lower()

        # استخراج الأرقام
        all_numbers = re.findall(r"\d+", full_text)

        # تحقق رقم الشركة
        is_company_ok = (
            company_phone in all_numbers
            or any(company_phone in n for n in all_numbers)
        )

        # تحقق المبلغ (تقريبي)
        amt_float = float(expected_amount)
        amt_main = str(int(amt_float))
        amt_rounded = str(round(amt_float))

        is_amount_ok = (
            any(amt_main in n for n in all_numbers)
            or any(amt_rounded in n for n in all_numbers)
            or str(amt_float) in full_text
        )

        # =========================
        # استخراج transaction_id بدون الاعتماد على تاريخ (غير ثابت)
        # =========================
        transaction_id = None

        # استبعاد رقم الشركة والمبلغ (حتى لا نلتقطهما كـ transaction_id)
        blocked = {company_phone, amt_main, amt_rounded}

        # مرشحون: أرقام طويلة (معرّف المعاملة عادةً طويل)
        candidates = [n for n in all_numbers if len(n) >= 10 and n not in blocked]

        if candidates:
            # خذ أطول رقم (غالباً هو معرّف المعاملة)
            transaction_id = max(candidates, key=len)
        else:
            # fallback: لو ما في أرقام طويلة، خذ أي رقم بطول >= 8 ليس رقم الشركة
            fallback = [n for n in all_numbers if len(n) >= 8 and n != company_phone]
            if fallback:
                transaction_id = max(fallback, key=len)

        ok = is_company_ok and is_amount_ok and (transaction_id is not None)
        return ok, transaction_id

    except Exception as e:
        print(f"OCR Error: {e}")
        return False, None


# =========================
# Billet/formulaire PDF (téléchargeable après la réservation) - Belle copie
# =========================

def _build_ticket_pdf(reservation) -> io.BytesIO:


    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    W, H = A4

    # ====== couleurs ======
    BLUE = colors.HexColor("#1677ff")
    LIGHT_BG = colors.HexColor("#f5f7fb")
    BORDER = colors.HexColor("#d9e2ef")
    TEXT = colors.HexColor("#0f172a")
    MUTED = colors.HexColor("#64748b")
    GREEN = colors.HexColor("#16a34a")

    # ====== Contexte général ======
    c.setFillColor(LIGHT_BG)
    c.rect(0, 0, W, H, stroke=0, fill=1)

    # ====== Barre latérale ======
    side_w = 1.0 * cm
    c.setFillColor(colors.HexColor("#0b4fb3"))
    c.rect(0, 0, side_w, H, stroke=0, fill=1)

    # ====== Header ======
    header_h = 3.2 * cm
    c.setFillColor(BLUE)
    c.roundRect(side_w + 1.2*cm, H - header_h - 1.2*cm, W - side_w - 2.4*cm, header_h, 18, stroke=0, fill=1)

    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(side_w + 2.0*cm, H - 2.2*cm, "TICKET DE VOYAGE - SGT")
    c.setFont("Helvetica", 11)
    c.drawString(side_w + 2.0*cm, H - 2.75*cm, "Société de Gestion de Transport")

    # ====== Card ======
    card_x = side_w + 1.2*cm
    card_y = 2.2*cm
    card_w = W - side_w - 2.4*cm
    card_h = H - header_h - 4.2*cm

    c.setFillColor(colors.white)
    c.setStrokeColor(BORDER)
    c.setLineWidth(1)
    c.roundRect(card_x, card_y, card_w, card_h, 16, stroke=1, fill=1)

    # ====== Données ======
    v = reservation.voyage
    t = v.trajet
    total = float(reservation.nb_sieges * v.prix_par_siege) if v.prix_par_siege is not None else 0.0

    left_x = card_x + 1.4*cm
    top_y = card_y + card_h - 1.3*cm

    right_x = card_x + card_w - 7.2*cm
    qr_size = 5.2*cm

    c.setFillColor(MUTED)
    c.setFont("Helvetica", 10)
    c.drawString(left_x, top_y, "Référence")

    c.setFillColor(TEXT)
    c.setFont("Helvetica-Bold", 16)
    ref = f"#{reservation.id_reservation}{v.date_depart.strftime('%Y%m%d')}"
    c.drawString(left_x, top_y - 0.65*cm, ref)

    c.setFillColor(MUTED)
    c.setFont("Helvetica", 10)
    c.drawString(left_x + 9.0*cm, top_y, "Date d'émission")

    c.setFillColor(TEXT)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(left_x + 9.0*cm, top_y - 0.65*cm, f"{reservation.date_reservation.strftime('%d/%m/%Y %H:%M')}")

    c.setStrokeColor(BORDER)
    c.line(card_x + 1.2*cm, top_y - 1.2*cm, card_x + card_w - 1.2*cm, top_y - 1.2*cm)

    y = top_y - 2.0*cm
    c.setFillColor(TEXT)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(left_x, y, "Itinéraire")

    box_y = y - 2.1*cm
    box_h = 2.0*cm
    c.setFillColor(colors.HexColor("#f8fafc"))
    c.setStrokeColor(BORDER)
    c.roundRect(left_x, box_y, card_w - 9.0*cm, box_h, 12, stroke=1, fill=1)

    c.setFillColor(MUTED)
    c.setFont("Helvetica", 10)
    c.drawString(left_x + 0.7*cm, box_y + 1.25*cm, "Départ")
    c.drawString(left_x + (card_w - 9.0*cm)/2 + 0.2*cm, box_y + 1.25*cm, "Arrivée")

    c.setFillColor(TEXT)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(left_x + 0.7*cm, box_y + 0.55*cm, f"{t.ville_depart}")
    c.drawString(left_x + (card_w - 9.0*cm)/2 + 0.2*cm, box_y + 0.55*cm, f"{t.ville_arrivee}")

    info_y = box_y - 1.6*cm
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 10)
    c.drawString(left_x, info_y + 0.9*cm, "Passager")
    c.drawString(left_x + 6.0*cm, info_y + 0.9*cm, "Sièges")
    c.drawString(left_x + 10.0*cm, info_y + 0.9*cm, "Prix Total")

    c.setFillColor(TEXT)
    c.setFont("Helvetica-Bold", 12)
    passenger = f"{reservation.client.username}" if hasattr(reservation, "client") and reservation.client else "-"
    c.drawString(left_x, info_y + 0.35*cm, passenger)
    c.drawString(left_x + 6.0*cm, info_y + 0.35*cm, str(reservation.nb_sieges))
    c.drawString(left_x + 10.0*cm, info_y + 0.35*cm, f"{total:.2f} MRU")

    badge_y = info_y - 1.4*cm
    c.setFillColor(GREEN)
    c.roundRect(right_x, badge_y + 0.2*cm, qr_size, 0.75*cm, 10, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(right_x + qr_size/2, badge_y + 0.47*cm, "PAIEMENT CONFIRMÉ")

    c.setFillColor(MUTED)
    c.setFont("Helvetica", 9.5)
    c.drawString(right_x, badge_y - 0.2*cm, "Transaction ID:")
    c.setFillColor(TEXT)
    c.setFont("Helvetica-Bold", 10.5)
    c.drawString(right_x, badge_y - 0.8*cm, f"{reservation.transaction_id or '-'}")

    try:
        qr_data = f"RES:{reservation.id_reservation}|TID:{reservation.transaction_id or ''}|TOTAL:{total:.2f}|TRAJET:{t.ville_depart}-{t.ville_arrivee}"
        qr_img = qrcode.make(qr_data)

        qr_buf = io.BytesIO()
        qr_img.save(qr_buf, format="PNG")
        qr_buf.seek(0)

        qr_reader = ImageReader(qr_buf)
        qr_y = top_y - 1.2*cm - qr_size
        c.drawImage(qr_reader, right_x, qr_y, qr_size, qr_size, mask="auto")

        c.setFillColor(MUTED)
        c.setFont("Helvetica", 9)
        c.drawCentredString(right_x + qr_size/2, qr_y - 0.35*cm, "QR Code")
    except Exception as e:
        print("QR skipped:", e)

    c.setFillColor(MUTED)
    c.setFont("Helvetica-Oblique", 10)
    c.drawString(card_x + 1.4*cm, card_y + 1.0*cm, "Merci pour votre confiance.")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer


from django.views.decorators.http import require_http_methods

@csrf_exempt
@require_http_methods(["GET", "POST"])
def api_mobile_reservations(request):
    """
    Endpoint compatible Flutter:
    - GET  /api/mobile/reservations/?user_id=1  => réservations utilisateur
    - POST /api/mobile/reservations/           => créer réservation
    """

    if request.method == "GET":
        user_id_str = (request.GET.get("user_id") or "").strip()

        # ✅ Évite ValueError: int("null") / int(" ")
        if not user_id_str.isdigit():
            return JsonResponse(
                {"status": "error", "message": "user_id requis et doit être numérique"},
                status=400
            )

        return api_mes_reservations_mobile(request, int(user_id_str))

    # POST
    return api_ajouter_reservation_mobile(request)



def api_mobile_ticket_pdf(request, id_reservation):
    res = get_object_or_404(Reservation, id_reservation=id_reservation)

    if not (res.statut == "confirmé" and res.statut_paiement == "paye"):
        return JsonResponse({
            "status": "error",
            "message": "Ticket disponible uniquement après validation."
        }, status=403)

    pdf_buffer = _build_ticket_pdf(res)  # ✅ ReportLab (بدون WeasyPrint)
    filename = f"ticket_{res.id_reservation}.pdf"

    return FileResponse(
        pdf_buffer,
        as_attachment=True,
        filename=filename,
        content_type="application/pdf",
    )

# =========================
# APIs Mobile (Flutter)
# =========================
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token

@csrf_exempt
def api_login_mobile(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Méthode non autorisée"}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
        user = authenticate(username=data.get("username"), password=data.get("password"))

        if not user:
            return JsonResponse({"status": "error", "message": "Identifiants incorrects"}, status=400)

        if not user.is_active:
            return JsonResponse({"status": "error", "message": "Compte désactivé"}, status=403)

        role = getattr(user, "role", "")

        # ✅ autoriser Client + Chauffeur sur mobile
        if role not in ("CLIENT", "CHAUFFEUR"):
            return JsonResponse({"status": "error", "message": "Accès mobile réservé aux clients et chauffeurs."}, status=403)

        # ✅ créer/retourner token DRF
        token, _ = Token.objects.get_or_create(user=user)

        return JsonResponse({
            "status": "success",
            "user_id": user.id,
            "username": user.username,
            "role": role,
            "token": token.key,
        })

    except Exception:
        return JsonResponse({"status": "error", "message": "Format invalide"}, status=400)

@csrf_exempt
def api_register_mobile(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Méthode non autorisée"}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""
        prenom = (data.get("prenom") or "").strip()
        nom = (data.get("nom") or "").strip()
        telephone = (data.get("telephone") or "").strip()
        email = (data.get("email") or "").strip()

        if not username or not password:
            return JsonResponse({"status": "error", "message": "Username et mot de passe requis"}, status=400)

        if User.objects.filter(username=username).exists():
            return JsonResponse({"status": "error", "message": "Nom d'utilisateur déjà utilisé"}, status=400)

        user = User.objects.create_user(username=username, password=password)
        user.role = "CLIENT"
        user.is_active = True

        user.first_name = prenom
        user.last_name = nom
        if email:
            user.email = email

        if hasattr(user, "telephone") and telephone:
            setattr(user, "telephone", telephone)

        user.save()

        return JsonResponse({"status": "success", "user_id": user.id, "username": user.username})

    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@csrf_exempt
def api_get_voyages_mobile(request):
    today = timezone.localdate()

    voyages = (
        Voyage.objects.select_related("trajet", "vehicule")
        .filter(date_depart__gte=today)
        .annotate(
            statut_db=SgtCheckStatutVoyage(F("id_voyage")),
            places_dispo=SgtSiegesDisponibles(F("id_voyage")),
        )
        .order_by("date_depart", "heure_depart")
    )

    data = []
    for v in voyages:
        if v.statut_db != "OUVERT":
            continue

        data.append({
            "id": v.id_voyage,
            "trajet": f"{v.trajet.ville_depart} -> {v.trajet.ville_arrivee}",
            "prix_par_siege": float(v.prix_par_siege or 0),
            "date": v.date_depart.strftime("%Y-%m-%d"),
            "heure": v.heure_depart.strftime("%H:%M"),
            "places_dispo": int(v.places_dispo or 0),
        })

    return JsonResponse(data, safe=False)



# ✅ NEW/UPDATED فقط
import os
import mimetypes
from django.http import Http404
from django.views.decorators.http import require_GET


# views.py (ONLY MODIFIED / ADDED PARTS)

import os
import uuid
from django.utils import timezone
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.db.models import Sum
from django.views.decorators.csrf import csrf_exempt

from .models import Voyage, Reservation
from django.contrib.auth import get_user_model

User = get_user_model()


# ✅ تعديل مهم: API السعر (حتى يشتغل كود JS الذي يستعمل data.prix)
@csrf_exempt
def api_get_voyage_price(request, id_voyage):
    v = get_object_or_404(Voyage, id_voyage=id_voyage)
    price = float(v.prix_par_siege or 0)

    return JsonResponse({
        "id_voyage": v.id_voyage,
        "prix_par_siege": price,
        "prix": price,  # ✅ مهم للـ JS في form.html
        "trajet": str(v.trajet),
        "date": v.date_depart.strftime("%Y-%m-%d"),
        "heure": v.heure_depart.strftime("%H:%M"),
    })


# ✅ تحسين بسيط: ترتيب الحجوزات (المنتظرة تظهر أولاً)
def liste_reservations(request):
    reservations = Reservation.objects.all().order_by("statut_paiement", "-date_reservation")
    return render(request, "reservations/liste.html", {"reservations": reservations})


# ✅✅✅ أهم تعديل: إنشاء حجز من Mobile = دائمًا en_attente + حفظ الصورة فعليًا
# views.py ✅ MODIFIED ONLY THIS FUNCTION

import json
import base64
import uuid

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.contrib import messages

from .models import Reservation, Voyage


User = get_user_model()


# ✅ دالة صغيرة: ترجع قيمة صحيحة من choices بدون ما تكسر المشروع
def safe_choice(model, field_name, preferred_values):
    """
    preferred_values: list مثل ['en_attente', 'en attente']
    ترجع أول قيمة موجودة فعلاً في choices.
    """
    field = model._meta.get_field(field_name)
    allowed = {c[0] for c in field.choices} if field.choices else set()

    for v in preferred_values:
        if v in allowed:
            return v

    # fallback: default إن كان موجود
    if hasattr(field, "default") and field.default in allowed:
        return field.default

    # fallback آخر: أول اختيار
    return next(iter(allowed)) if allowed else preferred_values[0]


# =========================================================
# ✅ (WEB) إضافة حجز من الويب => Payé مباشرة + Confirmé
# =========================================================
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .models import Reservation
from .forms import ReservationWebForm


from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .models import Reservation
from .forms import ReservationWebForm

User = get_user_model()


def _create_client_if_not_exists(nom: str, tel: str):
    """
    ✅ ينشئ Client جديد إذا لم يوجد
    - نحاول جعل username = الهاتف
    - إذا موجود نضيف رقم عشوائي صغير
    """
    base_username = tel.strip()
    username = base_username

    i = 1
    while User.objects.filter(username=username).exists():
        i += 1
        username = f"{base_username}_{i}"

    # إنشاء العميل
    user = User.objects.create_user(
        username=username,
        password=User.objects.make_random_password(),
    )

    # محاولة حفظ الاسم في first_name إن كان موجوداً
    try:
        user.first_name = nom
        user.save()
    except Exception:
        pass

    # محاولة حفظ الهاتف إذا كان في User (بعض المشاريع فيه phone أو telephone)
    for field_name in ["telephone", "phone", "tel"]:
        if hasattr(user, field_name):
            try:
                setattr(user, field_name, tel)
                user.save()
            except Exception:
                pass

    return user


from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model

from .models import Reservation
from .forms import ReservationWebForm


def _safe_decrease_places(voyage, nb):
    """
    ✅ ينقص places_dispo إذا كان الحقل موجوداً
    """
    if hasattr(voyage, "places_dispo"):
        try:
            voyage.places_dispo = int(voyage.places_dispo) - int(nb)
            if voyage.places_dispo < 0:
                voyage.places_dispo = 0
            voyage.save(update_fields=["places_dispo"])
        except Exception:
            pass


from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from .forms import ReservationWebForm
from .models import Reservation


@login_required
def ajouter_reservation(request):
    if request.method == "POST":
        form = ReservationWebForm(request.POST)

        if form.is_valid():
            client_mode = form.cleaned_data.get("client_mode")
            client = form.cleaned_data.get("client")
            autre_nom = form.cleaned_data.get("autre_nom")
            autre_tel = form.cleaned_data.get("autre_tel")
            voyage = form.cleaned_data.get("voyage")
            nb_sieges = form.cleaned_data.get("nb_sieges")
            mode_paiement = form.cleaned_data.get("mode_paiement")

            try:
                with transaction.atomic():
                    r = Reservation(
                        client=client,
                        autre_nom=autre_nom if client_mode == "other" else None,
                        autre_tel=autre_tel if client_mode == "other" else None,
                        voyage=voyage,
                        nb_sieges=nb_sieges,
                        cree_par=request.user
                    )

                    if hasattr(r, "mode_paiement"):
                        r.mode_paiement = mode_paiement


                    r.statut = "confirmé"
                    r.statut_paiement = "paye"

                    r.save()

                messages.success(request, "✅ Réservation ajoutée avec succès.")
                return redirect("liste_reservations")

            except DatabaseError as e:
                msg = str(e)

                if "Complet" in msg:
                    messages.error(request, "La voyage est complet, il n'y a pas assez de places.")
                elif "Voyage fermé" in msg:
                    messages.error(request, "La voyage fermée (moins de 30 minutes restantes).")
                else:
                    messages.error(request, f"Erreur lors de la création de la réservation: {msg}")

    else:
        form = ReservationWebForm()

    return render(request, "reservations/form.html", {"form": form})


from django.http import JsonResponse
from django.contrib.auth import get_user_model
from django.views.decorators.http import require_GET


@require_GET
def api_web_clients_search(request):
    q = (request.GET.get("q") or "").strip()
    User = get_user_model()

    qs = User.objects.all().order_by("username")

    if q:
        qs = qs.filter(username__icontains=q)

    qs = qs[:20]

    results = []
    for u in qs:
        results.append({
            "id": u.pk,
            "text": str(u.username)
        })

    return JsonResponse({"results": results})



@login_required
def modifier_reservation(request, id_reservation):
    res = get_object_or_404(Reservation, pk=id_reservation)

    if request.method == "POST":
        form = ReservationForm(request.POST, request.FILES, instance=res)
        if form.is_valid():
            form.save()
            return redirect("liste_reservations")
    else:

        form = ReservationForm(instance=res)

    return render(request, "reservations/form.html", {"form": form, "reservation": res})


# =========================================================
# ✅ (WEB) تأكيد الدفع من طرف المدير
# =========================================================
@login_required
def confirmer_paiement(request, id_reservation):
    r = get_object_or_404(Reservation, id_reservation=id_reservation)

    # ✅ عند التأكيد => Payé + Confirmé
    r.statut_paiement = safe_choice(Reservation, "statut_paiement", ["paye", "payé"])
    r.statut = safe_choice(Reservation, "statut", ["confirmé", "confirme", "confirmé"])
    r.save()

    messages.success(request, f"Paiement confirmé pour la réservation #{r.id_reservation}.")
    return redirect("liste_reservations")


import json, base64, uuid
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.files.base import ContentFile
from django.db import transaction, DatabaseError



@csrf_exempt
def api_ajouter_reservation_mobile(request):
    if request.method == "GET":
        return JsonResponse(
            {"status": "error", "message": "Utilisez POST pour créer une réservation."},
            status=405
        )

    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Méthode non autorisée"}, status=405)

    # ✅ Lire data (JSON ou form-data)
    data = {}
    try:
        if request.content_type and "application/json" in request.content_type:
            data = json.loads(request.body.decode("utf-8"))
        else:
            data = request.POST.dict()
    except Exception:
        data = request.POST.dict()

    # =========================
    # ✅ user_id (anti ValueError)
    # =========================
    client = None
    if request.user.is_authenticated:
        client = request.user
    else:
        user_id_str = str(data.get("user_id") or data.get("client_id") or "").strip()

        if not user_id_str.isdigit():
            return JsonResponse(
                {"status": "error", "message": "user_id invalide (doit être numérique)"},
                status=400
            )

        client = User.objects.filter(id=int(user_id_str)).first()

    if not client:
        return JsonResponse({"status": "error", "message": "Utilisateur introuvable"}, status=400)

    # =========================
    # ✅ voyage_id (anti ValueError)
    # =========================
    voyage_id_str = str(data.get("voyage_id") or data.get("id_voyage") or "").strip()
    if not voyage_id_str.isdigit():
        return JsonResponse(
            {"status": "error", "message": "voyage_id invalide (doit être numérique)"},
            status=400
        )

    voyage_id_int = int(voyage_id_str)

    voyage = (
        Voyage.objects.filter(id_voyage=voyage_id_int).first()
        or Voyage.objects.filter(id=voyage_id_int).first()
    )
    if not voyage:
        return JsonResponse({"status": "error", "message": "Voyage introuvable"}, status=404)

    # =========================
    # ✅ nb_sieges
    # =========================
    try:
        nb_sieges = int(data.get("nb_sieges") or data.get("sieges") or 1)
        if nb_sieges <= 0:
            nb_sieges = 1
    except Exception:
        nb_sieges = 1

    # ✅ (Mobile) دائمًا en attente
    statut_pending = safe_choice(Reservation, "statut", ["en_attente", "en attente"])
    paiement_pending = safe_choice(Reservation, "statut_paiement", ["en_attente", "en attente"])

    r = Reservation(
        client=client,
        voyage=voyage,
        nb_sieges=nb_sieges,
        statut=statut_pending,
        statut_paiement=paiement_pending,
    )

    # ======== preuve paiement (file أو base64) ========
    # 1) Multipart file
    if "preuve_paiement" in request.FILES:
        r.preuve_paiement = request.FILES["preuve_paiement"]

    # 2) base64 داخل JSON
    else:
        b64 = (
            data.get("preuve_paiement_base64")
            or data.get("preuve_base64")
            or data.get("image_base64")
        )

        if b64:
            try:
                if "base64," in b64:
                    b64 = b64.split("base64,")[-1]

                img_bytes = base64.b64decode(b64)
                filename = f"{uuid.uuid4().hex}.jpg"
                r.preuve_paiement.save(filename, ContentFile(img_bytes), save=False)
            except Exception:
                pass

    try:
        with transaction.atomic():
            r.save()
    except DatabaseError as e:
        msg = str(e)
        if "Complet" in msg:
            return JsonResponse({"status": "error", "message": "Voyage complet ❌"}, status=409)
        if "Voyage fermé" in msg:
            return JsonResponse({"status": "error", "message": "Voyage fermé (<30min) ❌"}, status=409)
        return JsonResponse({"status": "error", "message": msg}, status=400)

    # ✅ IMPORTANT: بدون هذا Django يرجع None => 500
    return JsonResponse(
        {
            "status": "success",
            "message": "Réservation envoyée ✅ En attente de validation.",
            "reservation_id": getattr(r, "id_reservation", None) or getattr(r, "id", None),
        },
        status=201
    )




from django.http import JsonResponse, FileResponse


import re
from decimal import Decimal, InvalidOperation


from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model

from django.views.decorators.http import require_GET

from .models import Reservation


# ===========================
# ✅ Helpers:
# ===========================
def _parse_decimal(value):

    if value is None:
        return None


    try:
        return Decimal(str(value))
    except Exception:
        pass

    # لو نص فيه رقم
    s = str(value).strip()
    if not s:
        return None

    # خذ أول رقم في النص
    match = re.search(r"[-+]?\d+[.,]?\d*", s)
    if not match:
        return None

    num = match.group(0).replace(",", ".")
    try:
        return Decimal(num)
    except (InvalidOperation, ValueError):
        return None


from decimal import Decimal
from django.urls import reverse

# ===========================
# Sérialiseur unifié pour mobile (avec total et date corrects)
# ===========================
def _serialize_reservation_mobile(r, request):
    voyage = getattr(r, "voyage", None)
    trajet = getattr(voyage, "trajet", None) if voyage else None

    rid = getattr(r, "id_reservation", None) or getattr(r, "id", None)

    raw_statut = str(getattr(r, "statut", "") or "")
    raw_paiement = str(getattr(r, "statut_paiement", "") or "")

    # ========== NORMALISATION (Display) ==========
    statut_display = raw_statut.strip()
    paiement_display = raw_paiement.strip()


    if raw_statut.lower().strip() in ["confirme", "confirmé", "confirmed"]:
        statut_display = "confirmé"
    elif raw_statut.lower().strip() in ["reserve", "réservé", "reservé", "reserved"]:
        statut_display = "réservé"


    if raw_paiement.lower().strip() in ["paye", "payé", "paid"]:
        paiement_display = "payé"
    elif raw_paiement.lower().strip() in ["en_attente", "en attente", "pending"]:
        paiement_display = "en_attente"
    elif raw_paiement.lower().strip() in ["echoue", "échoué", "failed"]:
        paiement_display = "echoue"

    # ========== CODES (sans accent) ==========
    statut_code = raw_statut.lower().strip()
    paiement_code = raw_paiement.lower().strip()

    if statut_code in ["confirmé"]:
        statut_code = "confirme"
    if paiement_code in ["payé"]:
        paiement_code = "paye"

    # ✅ ticket_ready
    ticket_ready = (statut_display == "confirmé" and paiement_display == "payé")


    ticket_url = None
    if ticket_ready and rid is not None:
        ticket_url = request.build_absolute_uri(
            reverse("api_mobile_ticket_pdf", args=[rid])
        )

    # ✅ proof url
    preuve_url = None
    if getattr(r, "preuve_paiement", None):
        try:
            preuve_url = request.build_absolute_uri(r.preuve_paiement.url)
        except Exception:
            preuve_url = None

    # ===========================
    # ✅ Total
    # ===========================
    nb = int(getattr(r, "nb_sieges", 1) or 1)

    unit_price = _find_unit_price(voyage) or _find_unit_price(trajet)

    total = None
    prix_unitaire = None
    try:
        if unit_price is not None:
            prix_unitaire = float(unit_price)
            total = float(Decimal(str(unit_price)) * Decimal(nb))
    except Exception:
        total = None
        prix_unitaire = None

    # ===========================
    # ✅ DATE FOR FLUTTER
    # ===========================
    date_depart_str = ""
    heure_depart_str = ""

    if voyage and getattr(voyage, "date_depart", None):
        try:
            date_depart_str = voyage.date_depart.strftime("%Y-%m-%d")
        except Exception:
            date_depart_str = ""

    if voyage and getattr(voyage, "heure_depart", None):
        try:
            heure_depart_str = voyage.heure_depart.strftime("%H:%M")
        except Exception:
            heure_depart_str = str(voyage.heure_depart)

    date_affiche = ""
    if date_depart_str and heure_depart_str:
        date_affiche = f"{date_depart_str} {heure_depart_str}"
    elif date_depart_str:
        date_affiche = date_depart_str

    return {
        "id_reservation": rid,

        "trajet": f"{trajet.ville_depart} -> {trajet.ville_arrivee}" if trajet else "",


        "date": date_affiche,

        "date_depart": date_depart_str,
        "heure_depart": heure_depart_str,

        "nb_sieges": nb,
        "date_reservation": r.date_reservation.strftime("%Y-%m-%d %H:%M:%S") if getattr(r, "date_reservation", None) else "",


        "statut": statut_display,
        "paiement": paiement_display,


        "statut_code": statut_code,
        "paiement_code": paiement_code,
        "statut_paiement": paiement_display,
        "statut_paiement_code": paiement_code,


        "preuve_paiement": preuve_url,

        # ✅ Ticket
        "ticket_ready": ticket_ready,
        "ticket": "disponible" if ticket_ready else "en_attente",
        "ticket_url": ticket_url,

        # ✅ Total
        "prix_unitaire": prix_unitaire,
        "total": total,


        "total_a_payer": total,
        "montant_total": total,
        "prix_total": total,
    }


# ===========================
# ✅ Helper
# ===========================
def _find_unit_price(obj):
    if obj is None:
        return None


    candidates = [
        "prix_par_siege", "prix_siege", "prix",
        "price", "unit_price", "tarif",
        "montant", "amount",
    ]

    for name in candidates:
        if hasattr(obj, name):
            val = getattr(obj, name, None)
            if val is not None:
                try:
                    return Decimal(str(val))
                except Exception:
                    try:
                        return Decimal(float(val))
                    except Exception:
                        return None

    return None

@require_GET
def api_mes_reservations_mobile(request, user_id):
    User = get_user_model()
    user = get_object_or_404(User, id=user_id)

    qs = (
        Reservation.objects
        .filter(client=user)
        .select_related("voyage", "voyage__trajet")
        .order_by("-date_reservation")
    )

    data = [_serialize_reservation_mobile(r, request) for r in qs]
    return JsonResponse(data, safe=False, status=200)


@require_GET
def api_mes_reservations_mobile_no_id(request):
    """
    ✅ حل إضافي لو Flutter يطلب endpoint بدون /id/
    GET /api/mobile/reservations/?user_id=23639
    """
    user_key = (request.GET.get("user_id") or "").strip()

    if not user_key.isdigit():
        # ✅ لازم List حتى لا ينهار Dart
        return JsonResponse([], safe=False, status=200)

    User = get_user_model()
    user = User.objects.filter(id=int(user_key)).first()

    if not user:
        return JsonResponse([], safe=False, status=200)

    qs = (
        Reservation.objects
        .filter(client=user)
        .select_related("voyage", "voyage__trajet")
        .order_by("-date_reservation")
    )

    data = [_serialize_reservation_mobile(r, request) for r in qs]
    return JsonResponse(data, safe=False, status=200)


# ✅ Endpoint جديد لتفادي 404 عند /api/mobile/reservations/
# GET /api/mobile/reservations/?user_id=12
# views.py  ✅ ONLY THIS FUNCTION MODIFIED

@csrf_exempt
def api_reservations_mobile(request):
    # ✅ POST => create reservation (mobile)
    if request.method == "POST":
        return api_ajouter_reservation_mobile(request)

    # ✅ GET => list reservations for one user
    if request.method == "GET":
        user_id = request.GET.get("user_id")
        if not user_id:
            return JsonResponse({"status": "error", "message": "user_id requis"}, status=400)

        return api_mes_reservations_mobile(request, int(user_id))

    return JsonResponse({"status": "error", "message": "Méthode non autorisée"}, status=405)


@superviseur_required
def voir_preuve_paiement(request, id_reservation):
    res = get_object_or_404(Reservation, id_reservation=id_reservation)

    if not res.preuve_paiement:
        raise Http404("Aucune preuve")

    file_path = res.preuve_paiement.path

    if not os.path.exists(file_path):
        raise Http404("Fichier preuve introuvable")

    content_type, _ = mimetypes.guess_type(file_path)
    return FileResponse(open(file_path, "rb"), content_type=content_type or "image/jpeg")




# =========================
# DRF API
# =========================
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .serializers import VoyageMobileSerializer

@api_view(["GET"])
def mobile_voyages(request):
    today = timezone.localdate()

    voyages = (
        Voyage.objects.select_related("trajet", "vehicule")
        .filter(date_depart__gte=today)
        .annotate(
            statut_db=SgtCheckStatutVoyage(F("id_voyage")),
            places_dispo=SgtSiegesDisponibles(F("id_voyage")),
        )
        .order_by("date_depart", "heure_depart")
    )

    voyages = [v for v in voyages if v.statut_db == "OUVERT"]

    serializer = VoyageMobileSerializer(voyages, many=True)
    return Response(serializer.data)


from django.http import JsonResponse
from .models import PaymentOption, CompanyContact

def api_mobile_payment_options(request):
    options = PaymentOption.objects.filter(is_active=True).order_by("order", "label")
    contact = CompanyContact.objects.filter(pk=1).first()

    data = {
        "whatsapp_number": (contact.whatsapp_number if contact else ""),
        "options": [
            {
                "code": o.code,
                "label": o.label,
                "phone_number": o.phone_number,
            }
            for o in options
        ]
    }
    return JsonResponse(data, safe=False)

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def chauffeur_voyages(request):
    # ✅ role عندك uppercase
    if getattr(request.user, "role", None) != "CHAUFFEUR":
        return Response({"detail": "Accès interdit"}, status=status.HTTP_403_FORBIDDEN)


    qs = Voyage.objects.filter(chauffeur__user=request.user).order_by("-date_depart", "-heure_depart")

    data = []
    for v in qs:
        data.append({
            "id_voyage": v.id_voyage,
            "trajet": str(v.trajet),
            "ville_depart": v.trajet.ville_depart,
            "ville_arrivee": v.trajet.ville_arrivee,
            "date_depart": str(v.date_depart),
            "heure_depart": str(v.heure_depart),
            "prix_par_siege": str(v.prix_par_siege),
            "sieges_disponibles": v.sieges_disponibles,
            "statut": v.check_statut,  # OUVERT / FERMÉ_...
            "vehicule": v.vehicule.matricule,
        })

    return Response(data)

import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from rest_framework.authtoken.models import Token

from .models import Voyage
from django.core.paginator import Paginator


@csrf_exempt
def api_chauffeur_voyages(request):
    # ✅ CORS preflight
    if request.method == "OPTIONS":
        return JsonResponse({}, status=200)

    if request.method != "GET":
        return JsonResponse({"status": "error", "message": "Méthode non autorisée"}, status=405)

    # ✅ Lire Token depuis Authorization header
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Token "):
        return JsonResponse({"status": "error", "message": "Token manquant"}, status=401)

    key = auth.replace("Token ", "").strip()
    if not key:
        return JsonResponse({"status": "error", "message": "Token vide"}, status=401)

    try:
        token_obj = Token.objects.select_related("user").get(key=key)
    except Token.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Token invalide"}, status=401)

    user = token_obj.user

    if not user.is_active:
        return JsonResponse({"status": "error", "message": "Compte désactivé"}, status=403)

    if getattr(user, "role", "") != "CHAUFFEUR":
        return JsonResponse({"status": "error", "message": "Accès réservé au chauffeur"}, status=403)

    # ✅ voyages assignés à ce chauffeur (via Chauffeur.user)
    qs = Voyage.objects.filter(chauffeur__user=user).select_related("trajet", "vehicule", "chauffeur").order_by("-date_depart", "-heure_depart")

    # =========================
    # Pagination
    # =========================
    page = int(request.GET.get("page", 1))
    page_size = int(request.GET.get("page_size", 10))

    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(page)

    results = []
    for v in page_obj.object_list:
        results.append({
            "id_voyage": v.id_voyage,
            "ville_depart": v.trajet.ville_depart if v.trajet else "",
            "ville_arrivee": v.trajet.ville_arrivee if v.trajet else "",
            "date_depart": v.date_depart.strftime("%Y-%m-%d") if v.date_depart else "",
            "heure_depart": v.heure_depart.strftime("%H:%M") if v.heure_depart else "",
            "vehicule_matricule": v.vehicule.matricule if v.vehicule else "",
            "statut": getattr(v, "check_statut", ""),
        })

    return JsonResponse({
        "count": paginator.count,
        "page": page_obj.number,
        "page_size": page_size,
        "has_next": page_obj.has_next(),
        "results": results,
    }, status=200)

