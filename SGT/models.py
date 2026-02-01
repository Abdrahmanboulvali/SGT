from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal


class Trajet(models.Model):
    id_trajet = models.AutoField(primary_key=True, db_column='id_trajet')
    ville_depart = models.CharField(max_length=100, db_column='ville_depart')
    ville_arrivee = models.CharField(max_length=100, db_column='ville_arrivee')
    distance_km = models.DecimalField(max_digits=6, decimal_places=2, db_column='distance_km')
    duree_prevue = models.DurationField(null=True, blank=True, db_column='duree_prevue')

    class Meta:
        db_table = 'trajet'
        managed = True

    def __str__(self):
        return f"{self.ville_depart} -> {self.ville_arrivee}"


class Vehicule(models.Model):
    id_vehicule = models.AutoField(primary_key=True, db_column='id_vehicule')
    matricule = models.CharField(max_length=20, unique=True, db_column='matricule')
    capacite = models.PositiveIntegerField(db_column='capacite')
    type = models.CharField(max_length=50, db_column='type')
    kilometrage_total = models.DecimalField(max_digits=10, decimal_places=2, db_column='kilometrage_total')

    class Meta:
        db_table = 'vehicule'
        managed = True

    def __str__(self):
        return self.matricule


class Chauffeur(models.Model):
    id_chauffeur = models.AutoField(primary_key=True, db_column='id_chauffeur')
    nom = models.CharField(max_length=100, db_column='nom')
    telephone = models.CharField(max_length=20, null=True, blank=True, db_column='telephone')

    class Meta:
        db_table = 'chauffeur'
        managed = True

    def __str__(self):
        return self.nom


class User(AbstractUser):
    ROLE_CHOICES = (('ADMIN', 'Admin'), ('AGENT', 'Agent'), ('CLIENT', 'Client'), ('SUPERVISEUR', 'Superviseur'))
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='CLIENT', db_column='role')
    telephone = models.CharField(max_length=20, null=True, blank=True, db_column='telephone')

    class Meta:
        db_table = 'utilisateur'
        managed = True


from decimal import Decimal
from datetime import datetime, timedelta

from django.db import models
from django.utils import timezone
from django.db.models import Sum
from django.db.models.functions import Coalesce


class Voyage(models.Model):
    id_voyage = models.AutoField(primary_key=True, db_column='id_voyage')
    date_depart = models.DateField(db_column='date_depart')
    heure_depart = models.TimeField(db_column='heure_depart')

    prix_par_siege = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('1.50'),
        db_column='prix_par_siege'
    )

    trajet = models.ForeignKey(
        "Trajet",
        on_delete=models.CASCADE,
        db_column='id_trajet',
        related_name='voyages'
    )
    vehicule = models.ForeignKey(
        "Vehicule",
        on_delete=models.CASCADE,
        db_column='id_vehicule',
        related_name='voyages'
    )
    chauffeur = models.ForeignKey(
        "Chauffeur",
        on_delete=models.CASCADE,
        db_column='id_chauffeur',
        related_name='voyages'
    )

    class Meta:
        db_table = 'voyage'
        managed = True

    # ✅✅✅ دمج تاريخ + وقت الرحلة (مفيد للفورم والـ list)
    @property
    def depart_datetime(self):
        tz = timezone.get_current_timezone()
        return timezone.make_aware(datetime.combine(self.date_depart, self.heure_depart), tz)

    @property
    def check_statut(self):
        """
        ✅ الرحلة تُغلق في حالتين:
        1) بقي 30 دقيقة أو أقل
        2) ممتلئة (المقاعد المحجوزة >= سعة المركبة)
        """
        now = timezone.localtime()
        dt_depart = self.depart_datetime

        if dt_depart <= (now + timedelta(minutes=30)):
            return "FERMÉ_TEMPS"

        total_res = self.reservations.exclude(statut='annulé').aggregate(
            total=Coalesce(Sum('nb_sieges'), 0)
        )['total']

        if total_res >= self.vehicule.capacite:
            return "FERMÉ_COMPLET"

        return "OUVERT"

    # ✅✅✅ المقاعد المحجوزة والمتاحة (كما عندك)
    @property
    def sieges_reserves(self) -> int:
        total = self.reservations.exclude(statut='annulé').aggregate(
            total=Coalesce(Sum('nb_sieges'), 0)
        )['total']
        return int(total or 0)

    @property
    def sieges_disponibles(self) -> int:
        return max(int(self.vehicule.capacite) - self.sieges_reserves, 0)

    # ✅✅✅ (جديد) Boolean جاهز للاستعمال في الفورم والواجهة
    @property
    def est_ferme(self) -> bool:
        return self.check_statut != "OUVERT"

    # ✅✅✅ (جديد) سبب الإغلاق للعرض في صفحة الرحلات
    @property
    def raison_fermeture(self) -> str:
        if self.check_statut == "FERMÉ_COMPLET":
            return "Complet (0 place disponible)"
        if self.check_statut == "FERMÉ_TEMPS":
            return "Délai (<30min) dépassé"
        return ""

    def __str__(self):
        return (
            f"{self.trajet.ville_depart} -> {self.trajet.ville_arrivee} | "
            f"{self.date_depart.strftime('%Y-%m-%d')} {self.heure_depart.strftime('%H:%M')} | "
            f"Vehicule: {self.vehicule.matricule} - {self.vehicule.type} | "
            f"Places dispo: {self.sieges_disponibles}"
        )



class Reservation(models.Model):
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )


    autre_nom = models.CharField(max_length=120, null=True, blank=True)
    autre_tel = models.CharField(max_length=30, null=True, blank=True)


    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="reservations_creees"
    )

    STATUT_CHOICES = [('réservé', 'Réservé'), ('confirmé', 'Confirmé'), ('annulé', 'Annulé'), ('payé', 'Payé')]

    id_reservation = models.AutoField(primary_key=True, db_column='id_reservation')
    voyage = models.ForeignKey(Voyage, on_delete=models.CASCADE, db_column='id_voyage', related_name='reservations')
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='id_client'
    )
    nb_sieges = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='réservé')
    date_reservation = models.DateTimeField(auto_now_add=True)

    preuve_paiement = models.ImageField(upload_to='paiements/', null=True, blank=True)
    transaction_id = models.CharField(max_length=100, null=True, blank=True, unique=True)
    statut_paiement = models.CharField(max_length=20, default='en_attente')
    METHODE_PAIEMENT_CHOICES = [
        ("bankily", "Bankily"),
        ("masrvi", "Masrvi"),
        ("sedad", "Sedad"),
        ("ghaza_pay", "Ghaza Pay"),
        ("bii", "Bii"),
        ("moov_money", "Moov Money"),
    ]

    methode_paiement = models.CharField(
        max_length=30,
        choices=METHODE_PAIEMENT_CHOICES,
        default="bankily",
        blank=True,
        null=True
    )
    class Meta:
        db_table = 'reservation'
        managed = True

    @property
    def prix_unitaire(self) -> Decimal:
        # ✅ حماية: إذا voyage غير موجود بعد
        if not getattr(self, "voyage_id", None):
            return Decimal("0")
        return self.voyage.prix_par_siege or Decimal("0")

    @property
    def montant_total(self) -> Decimal:
        # ✅ حماية: إذا voyage غير موجود بعد
        if not getattr(self, "voyage_id", None):
            return Decimal("0.00")
        return (self.prix_unitaire * Decimal(self.nb_sieges or 0)).quantize(Decimal("0.01"))

    def clean(self):
        # ✅✅✅ إصلاح الخطأ: إذا لم يتم اختيار voyage بعد، لا نكمل clean
        # هذا يمنع: RelatedObjectDoesNotExist (Reservation has no voyage)
        if not getattr(self, "voyage_id", None):
            return

        if self.statut == "annulé":
            return
        # ✅ حماية إضافية: إذا nb_sieges غير موجود/فارغ
        if not self.nb_sieges:
            return

        if self.statut != 'annulé':
            if self.voyage.check_statut == "FERMÉ_TEMPS":
                raise ValidationError("Voyage fermé (Temps écoulé).")

            total_res = self.voyage.reservations.exclude(pk=self.pk).exclude(statut='annulé').aggregate(
                total=Coalesce(Sum('nb_sieges'), 0)
            )['total']

            if (total_res + self.nb_sieges) > self.voyage.vehicule.capacite:
                raise ValidationError(f"Complet! Places restantes: {self.voyage.vehicule.capacite - total_res}")

    def save(self, *args, **kwargs):
        # ✅ مزامنة statut مع statut_paiement تلقائياً
        if self.statut in ("confirmé", "payé"):
            self.statut = "confirmé"
            self.statut_paiement = "paye"
        elif self.statut == "annulé":
            self.statut_paiement = "en_attente"
        else:
            # réservé
            self.statut_paiement = "en_attente"

        self.full_clean()
        super().save(*args, **kwargs)

from django.db import models

class PaymentOption(models.Model):

    code = models.SlugField(max_length=50, unique=True)
    label = models.CharField(max_length=60)
    phone_number = models.CharField(max_length=30)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "label"]

    def __str__(self):
        return f"{self.label} ({self.phone_number})"


class CompanyContact(models.Model):

    whatsapp_number = models.CharField(max_length=30, blank=True, default="")

    def save(self, *args, **kwargs):

        self.pk = 1
        super().save(*args, **kwargs)

    def __str__(self):
        return f"WhatsApp: {self.whatsapp_number or '—'}"
