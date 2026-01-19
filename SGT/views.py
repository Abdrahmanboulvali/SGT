# views.py
from functools import wraps
from django.core.exceptions import PermissionDenied

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, get_user_model, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
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

# ✅ إضافات مطلوبة لتنزيل الاستمارة PDF بعد الحجز (بدون حذف أي شيء من كودك)
import io
from django.http import FileResponse

from .models import Vehicule, Chauffeur, Trajet, Voyage, Reservation
from .forms import (
    VehiculeForm, ChauffeurForm, TrajetForm,
    VoyageForm, ReservationForm, LoginForm, RegisterForm, ClientForm
)

User = get_user_model()


# =========================
# OCR (تحقق الدفع بالصورة)
# =========================

_reader = None

def get_reader():
    """تحميل قارئ OCR مرة واحدة فقط (Lazy Loading)."""
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
        # استخراج transaction_id بدون الاعتماد على 02/08 (لأنه غير ثابت)
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
# ✅ PDF Ticket / Form (للتحميل بعد الحجز) - نسخة جميلة
# =========================

import io
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import cm
import qrcode
from PIL import Image

from .models import Reservation


def _generate_qr_image(data: str):
    """إنشاء QR Code كصورة PIL"""
    qr = qrcode.QRCode(
        version=2,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    return img


import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors

def _build_ticket_pdf(reservation) -> io.BytesIO:
    """
    PDF Ticket محسّن بالشكل (header + card + badge + QR).
    """
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    W, H = A4

    # ====== ألوان ======
    BLUE = colors.HexColor("#1677ff")      # قريب من تصميم الويب
    LIGHT_BG = colors.HexColor("#f5f7fb")
    BORDER = colors.HexColor("#d9e2ef")
    TEXT = colors.HexColor("#0f172a")
    MUTED = colors.HexColor("#64748b")
    GREEN = colors.HexColor("#16a34a")

    # ====== خلفية عامة ======
    c.setFillColor(LIGHT_BG)
    c.rect(0, 0, W, H, stroke=0, fill=1)

    # ====== شريط جانبي بسيط ======
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

    # ====== بيانات ======
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
        import qrcode
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


def api_mobile_ticket_pdf(request, id_reservation):
    """
    GET /api/mobile/ticket/<id_reservation>/
    يرجع PDF جميل للتذكرة.
    """
    res = get_object_or_404(Reservation, id_reservation=id_reservation)
    pdf_buffer = _build_ticket_pdf(res)

    filename = f"ticket_{res.id_reservation}.pdf"
    return FileResponse(
        pdf_buffer,
        as_attachment=True,
        filename=filename,
        content_type="application/pdf",
    )


# =========================
# Helpers (صلاحيات)
# =========================

def is_superviseur(user):
    """
    ✅ التعديل المطلوب:
    - السماح دائمًا للـ Admin الحقيقي (superuser/staff)
    - حتى لو كانت قيمة role = CLIENT بالخطأ
    """
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

            # ✅ منع الزبون من دخول الويب (لكن اسمح للـ Admin/Staff دائمًا)
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
    now = timezone.now()
    threshold = now + timedelta(minutes=30)

    voyages = Voyage.objects.all().order_by('-date_depart', '-heure_depart')

    voyage_data = []
    for v in voyages:
        reserved = (
            Reservation.objects
            .filter(voyage=v)
            .exclude(statut="annulé")
            .aggregate(s=Sum("nb_sieges"))["s"] or 0
        )
        seats_left = max(v.vehicule.capacite - reserved, 0)

        is_time_ok = (
            (v.date_depart > threshold.date()) or
            (v.date_depart == threshold.date() and v.heure_depart > threshold.time())
        )
        is_open = (seats_left > 0) and is_time_ok

        voyage_data.append({
            "obj": v,
            "seats_left": seats_left,
            "is_open": is_open,
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


@csrf_exempt
def api_get_voyage_price(request, id_voyage):
    v = get_object_or_404(Voyage, id_voyage=id_voyage)
    return JsonResponse({
        "id_voyage": v.id_voyage,
        "prix_par_siege": float(v.prix_par_siege),
        "trajet": str(v.trajet),
        "date": v.date_depart.strftime("%Y-%m-%d"),
        "heure": v.heure_depart.strftime("%H:%M"),
    })


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
def liste_reservations(request):
    reservations = Reservation.objects.all().order_by("-date_reservation")
    return render(request, "reservations/liste.html", {"reservations": reservations})


@login_required
def mes_reservations(request):
    if getattr(request.user, "role", "") != "CLIENT":
        messages.error(request, "Accès غير مسموح.")
        return redirect("dashboard")
    reservations = Reservation.objects.filter(client=request.user).order_by("-date_reservation")
    return render(request, "reservations/mes_reservations.html", {"reservations": reservations})


@login_required
def ajouter_reservation(request):
    if request.method == "POST":
        data = request.POST.copy()

        if getattr(request.user, "role", "") == "CLIENT":
            data["client"] = request.user.id

        form = ReservationForm(data, request.FILES)

        if form.is_valid():
            v = form.cleaned_data["voyage"]
            n = form.cleaned_data["nb_sieges"]

            reserved = (
                Reservation.objects.filter(voyage=v)
                .exclude(statut="annulé")
                .aggregate(s=Sum("nb_sieges"))["s"] or 0
            )
            available = v.vehicule.capacite - reserved
            if n > available:
                messages.error(request, f"Places insuffisantes. Disponible: {available}")
                return render(request, "reservations/form.html", {"form": form})

            total_price_expected = float(v.prix_par_siege * n)

            if getattr(request.user, "role", "") == "CLIENT":
                if "preuve_paiement" not in request.FILES:
                    messages.error(request, "Preuve de paiement requise.")
                    return render(request, "reservations/form.html", {"form": form})

                image_file = request.FILES["preuve_paiement"]
                ok, tid = verify_payment_ocr(image_file, total_price_expected)

                if ok and tid:
                    if Reservation.objects.filter(transaction_id=tid).exists():
                        messages.error(request, "Transaction déjà utilisée.")
                        return render(request, "reservations/form.html", {"form": form})

                    res = form.save(commit=False)
                    res.transaction_id = tid
                    res.statut_paiement = "paye"
                    res.statut = "confirmé"
                    res.save()

                    messages.success(request, f"Succès! ID: {tid}")
                    return redirect("ticket_reservation", id_reservation=res.id_reservation)

                messages.error(request, "Échec de validation OCR.")
                return render(request, "reservations/form.html", {"form": form})

            else:
                res = form.save(commit=False)

                if res.statut in ("confirmé", "payé"):
                    res.statut = "confirmé"
                    res.statut_paiement = "paye"
                else:
                    res.statut_paiement = "en_attente"

                res.save()

                messages.success(request, "Réservation ajoutée avec succès.")
                return redirect("ticket_reservation", id_reservation=res.id_reservation)

        return render(request, "reservations/form.html", {"form": form})

    else:
        form = ReservationForm()

    return render(request, "reservations/form.html", {"form": form})


@login_required
def modifier_reservation(request, id_reservation):
    res = get_object_or_404(Reservation, id_reservation=id_reservation)
    if request.method == "POST":
        form = ReservationForm(request.POST, request.FILES, instance=res)
        if form.is_valid():
            res = form.save(commit=False)

            if res.statut in ("confirmé", "payé"):
                res.statut = "confirmé"
                res.statut_paiement = "paye"
            elif res.statut == "annulé":
                res.statut_paiement = "en_attente"
            else:
                res.statut_paiement = "en_attente"

            res.save()
            messages.success(request, "Réservation mise à jour.")
            return redirect("liste_reservations")

    else:
        form = ReservationForm(instance=res)
    return render(request, "reservations/form.html", {"form": form, "title": "Modifier Réservation"})


@login_required
def supprimer_reservation(request, id_reservation):
    res = get_object_or_404(Reservation, id_reservation=id_reservation)
    res.delete()
    messages.warning(request, "Réservation supprimée.")
    return redirect("liste_reservations")


@login_required
def ticket_reservation(request, id_reservation):
    res = get_object_or_404(Reservation, id_reservation=id_reservation)
    return render(request, "reservations/ticket.html", {
        "reservation": res,
        "res": res,
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


# ✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅
# ✅ الإصلاح التام هنا:
# استبدلنا user_passes_test(...raise_exception=True)
# بـ superviseur_required (لأن raise_exception غير مدعوم)
# ✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅
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
    allowed_roles = {"CLIENT", "SUPERVISEUR", "ADMIN", "STAFF"}
    if new_role not in allowed_roles:
        messages.error(request, "Rôle غير صالح.")
        return redirect("gestion_comptes")

    u = get_object_or_404(User, id=user_id)
    u.role = new_role
    u.save()
    messages.success(request, "Rôle modifié.")
    return redirect("gestion_comptes")


# =========================
# APIs Mobile (Flutter)
# =========================

@csrf_exempt
def api_login_mobile(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Méthode non autorisée"}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
        user = authenticate(username=data.get("username"), password=data.get("password"))
        if user:
            return JsonResponse({
                "status": "success",
                "user_id": user.id,
                "username": user.username,
                "role": getattr(user, "role", "")
            })
        return JsonResponse({"status": "error", "message": "Identifiants incorrects"}, status=400)
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
        .order_by("date_depart", "heure_depart")
    )

    data = []
    for v in voyages:
        if v.check_statut != "OUVERT":
            continue

        reserved = (
            Reservation.objects.filter(voyage=v)
            .exclude(statut="annulé")
            .aggregate(s=Sum("nb_sieges"))["s"] or 0
        )
        seats_left = max(v.vehicule.capacite - reserved, 0)

        data.append({
            "id": v.id_voyage,
            "trajet": f"{v.trajet.ville_depart} -> {v.trajet.ville_arrivee}",
            "prix_par_siege": float(v.prix_par_siege or 0),
            "date": v.date_depart.strftime("%Y-%m-%d"),
            "heure": v.heure_depart.strftime("%H:%M"),
            "places_dispo": seats_left,
        })

    return JsonResponse(data, safe=False)


@csrf_exempt
def api_ajouter_reservation_mobile(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Méthode non autorisée"}, status=405)

    try:
        v_id = request.POST.get("voyage_id")
        u_id = request.POST.get("client_id")
        seats_raw = request.POST.get("nb_sieges")
        preuve = request.FILES.get("preuve_paiement")

        if not v_id or not u_id or not seats_raw:
            return JsonResponse({"status": "error", "message": "Paramètres manquants"}, status=400)

        if not preuve:
            return JsonResponse({"status": "error", "message": "Preuve de paiement requise"}, status=400)

        user = get_object_or_404(User, id=u_id)
        if getattr(user, "role", "") != "CLIENT":
            return JsonResponse({"status": "error", "message": "Accès refusé (CLIENT فقط)"}, status=403)

        seats = int(seats_raw)
        if seats <= 0:
            return JsonResponse({"status": "error", "message": "nb_sieges invalide"}, status=400)

        voyage = get_object_or_404(Voyage, id_voyage=v_id)

        if voyage.check_statut != "OUVERT":
            return JsonResponse({"status": "error", "message": "Voyage fermé"}, status=400)

        reserved = (
            Reservation.objects.filter(voyage=voyage)
            .exclude(statut="annulé")
            .aggregate(s=Sum("nb_sieges"))["s"] or 0
        )
        available = voyage.vehicule.capacite - reserved
        if seats > available:
            return JsonResponse(
                {"status": "error", "message": f"Places insuffisantes. Disponible: {available}"},
                status=400
            )

        total = float(voyage.prix_par_siege * seats)

        ok, tid = verify_payment_ocr(preuve, total)
        if not (ok and tid):
            return JsonResponse({"status": "error", "message": "Paiement non reconnu"}, status=400)

        if Reservation.objects.filter(transaction_id=tid).exists():
            return JsonResponse({"status": "error", "message": "Transaction déjà utilisée"}, status=400)

        res = Reservation.objects.create(
            voyage=voyage,
            client=user,
            nb_sieges=seats,
            preuve_paiement=preuve,
            transaction_id=tid,
            statut_paiement="paye",
            statut="confirmé",
        )

        ticket_url = request.build_absolute_uri(f"/api/mobile/ticket/{res.id_reservation}/")

        return JsonResponse({
            "status": "success",
            "tid": tid,
            "reservation_id": res.id_reservation,
            "ticket_url": ticket_url
        }, status=201)

    except ValueError:
        return JsonResponse({"status": "error", "message": "nb_sieges doit être un entier"}, status=400)
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@csrf_exempt
def api_mes_reservations_mobile(request, user_id):
    res_list = Reservation.objects.filter(client_id=user_id).order_by("-date_reservation")
    data = []
    for r in res_list:
        prix_total = float(r.nb_sieges * r.voyage.prix_par_siege) if r.voyage.prix_par_siege is not None else 0.0
        data.append({
            "id": r.id_reservation,
            "trajet": str(r.voyage.trajet),
            "date": r.voyage.date_depart.strftime("%Y-%m-%d"),
            "statut": r.statut,
            "prix_total": prix_total,
            "ticket_url": f"http://10.9.164.178:8000/api/mobile/ticket/{r.id_reservation}/",
        })
    return JsonResponse(data, safe=False)


from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.utils import timezone
from datetime import datetime
from .models import Voyage
from .serializers import VoyageMobileSerializer


@api_view(["GET"])
def mobile_voyages(request):
    """
    يرجع الرحلات المفتوحة + المقاعد المتاحة
    """
    today = timezone.localdate()

    voyages = (
        Voyage.objects.select_related("trajet", "vehicule")
        .filter(date_depart__gte=today)
        .order_by("date_depart", "heure_depart")
    )

    voyages = [v for v in voyages if v.check_statut == "OUVERT"]

    serializer = VoyageMobileSerializer(voyages, many=True)
    return Response(serializer.data)
