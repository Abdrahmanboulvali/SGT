from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import get_user_model
from .models import Vehicule, Chauffeur, Trajet, Voyage, Reservation
from django.utils import timezone
from django.db.models import Q

User = get_user_model()

class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Identifiant",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom d\'utilisateur ou Téléphone'})
    )
    password = forms.CharField(
        label="Mot de passe",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Mot de passe'})
    )

class RegisterForm(forms.ModelForm):
    first_name = forms.CharField(
        label="Prénom",
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Votre prénom'})
    )
    last_name = forms.CharField(
        label="Nom",
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Votre nom'})
    )
    telephone = forms.CharField(
        label="Téléphone",
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 36xxxxxx'})
    )
    email = forms.EmailField(
        label="Email",
        required=False,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'exemple@email.com'})
    )
    password = forms.CharField(
        label="Mot de passe",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Mot de passe'})
    )
    password_confirm = forms.CharField(
        label="Confirmer le mot de passe",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirmer le mot de passe'})
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom d\'utilisateur'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get("password")
        p2 = cleaned_data.get("password_confirm")
        if p1 and p2 and p1 != p2:
            self.add_error('password_confirm', "Les mots de passe ne correspondent pas.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        user.first_name = self.cleaned_data.get("first_name")
        user.last_name = self.cleaned_data.get("last_name")
        if hasattr(user, 'phone'):
            user.phone = self.cleaned_data.get("telephone")
        elif hasattr(user, 'telephone'):
            user.telephone = self.cleaned_data.get("telephone")
        if commit:
            user.save()
        return user

class ClientForm(forms.ModelForm):
    first_name = forms.CharField(
        label="Prénom",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Mohamed'})
    )
    last_name = forms.CharField(
        label="Nom",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Ahmed'})
    )
    telephone = forms.CharField(
        label="Téléphone (Sera l'identifiant)",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 36xxxxxx'})
    )
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'client@example.com'})
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']

    def clean_telephone(self):
        tel = self.cleaned_data.get('telephone')
        if User.objects.filter(username=tel).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Ce numéro est déjà utilisé comme identifiant.")
        return tel

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data['telephone']
        if not user.pk:
            user.set_password('123456')
        if hasattr(user, 'phone'):
            user.phone = self.cleaned_data['telephone']
        elif hasattr(user, 'telephone'):
            user.telephone = self.cleaned_data['telephone']
        if commit:
            user.save()
        return user

class VehiculeForm(forms.ModelForm):
    class Meta:
        model = Vehicule
        fields = ['matricule', 'capacite', 'type', 'kilometrage_total']
        widgets = {
            'matricule': forms.TextInput(attrs={'class': 'form-control'}),
            'capacite': forms.NumberInput(attrs={'class': 'form-control'}),
            'type': forms.TextInput(attrs={'class': 'form-control'}),
            'kilometrage_total': forms.NumberInput(attrs={'class': 'form-control'}),
        }

class ChauffeurForm(forms.ModelForm):
    class Meta:
        model = Chauffeur
        fields = ['nom', 'telephone']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'telephone': forms.TextInput(attrs={'class': 'form-control'}),
        }

class TrajetForm(forms.ModelForm):
    class Meta:
        model = Trajet
        fields = ['ville_depart', 'ville_arrivee', 'distance_km', 'duree_prevue']
        widgets = {
            'ville_depart': forms.TextInput(attrs={'class': 'form-control'}),
            'ville_arrivee': forms.TextInput(attrs={'class': 'form-control'}),
            'distance_km': forms.NumberInput(attrs={'class': 'form-control'}),
            'duree_prevue': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'HH:MM:SS'}),
        }

class VoyageForm(forms.ModelForm):
    class Meta:
        model = Voyage
        fields = ['trajet', 'vehicule', 'chauffeur', 'date_depart', 'heure_depart', 'prix_par_siege']
        widgets = {
            'trajet': forms.Select(attrs={'class': 'form-select'}),
            'vehicule': forms.Select(attrs={'class': 'form-select'}),
            'chauffeur': forms.Select(attrs={'class': 'form-select'}),
            'date_depart': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'heure_depart': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'prix_par_siege': forms.NumberInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['vehicule'].label_from_instance = lambda v: f"{v.matricule} - {v.type}"


class ReservationForm(forms.ModelForm):
    preuve_paiement = forms.ImageField(
        required=False,
        label="Capture d'écran du paiement",
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'})
    )

    class Meta:
        model = Reservation
        fields = [
            'client',
            'voyage',
            'nb_sieges',
            'methode_paiement',
            'statut',
            'preuve_paiement'
        ]
        widgets = {
            'client': forms.Select(attrs={'class': 'form-select'}),
            'voyage': forms.Select(attrs={'class': 'form-select'}),
            'nb_sieges': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'methode_paiement': forms.Select(attrs={'class': 'form-select'}),
            'statut': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['statut'].required = False

        today = timezone.now().date()
        self.fields['voyage'].queryset = Voyage.objects.filter(
            date_depart__gte=today
        ).order_by('date_depart', 'heure_depart')

        self.fields['client'].empty_label = "Sélectionnez un client..."
        self.fields['voyage'].empty_label = "Sélectionnez un voyage..."




import re



def _to_int(x):
    try:
        if x is None:
            return None
        return int(float(str(x).strip()))
    except Exception:
        return None


def _extract_places_from_string(s: str):


    if not s:
        return None
    m = re.search(r"Places\s*dispo\s*:\s*(\d+)", s, re.IGNORECASE)
    if m:
        return _to_int(m.group(1))
    return None


def _get_places_dispo(v):
    """
    يرجع عدد المقاعد المتاحة مهما كان اسم الحقل أو طريقة الحساب.
    """
    possible_attrs = [
        "places_dispo", "place_dispo",
        "places_disponibles", "places_restantes",
        "nb_places_dispo", "nb_places_restantes",
    ]
    for attr in possible_attrs:
        val = getattr(v, attr, None)
        val_int = _to_int(val)
        if val_int is not None:
            return val_int

    possible_methods = [
        "get_places_dispo", "get_places_disponibles",
        "places_disponibles", "places_restantes",
    ]
    for m in possible_methods:
        fn = getattr(v, m, None)
        if callable(fn):
            try:
                val_int = _to_int(fn())
                if val_int is not None:
                    return val_int
            except Exception:
                pass

    return _extract_places_from_string(str(v))


def _get_departure_dt(v):
    """
    دمج date_depart + heure_depart
    """
    if not getattr(v, "date_depart", None) or not getattr(v, "heure_depart", None):
        return None
    try:
        dt = datetime.combine(v.date_depart, v.heure_depart)
        # إذا كانت timezone مفعلّة
        if timezone.is_aware(timezone.now()):
            return timezone.make_aware(dt) if timezone.is_naive(dt) else dt
        return dt
    except Exception:
        return None


from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Sum
from datetime import datetime, timedelta

from .models import Reservation, Voyage

User = get_user_model()


from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone

from datetime import timedelta

from .models import Reservation, Voyage

User = get_user_model()


class ReservationWebForm(forms.ModelForm):

    client_mode = forms.ChoiceField(
        choices=[
            ("existing", "Client existant"),
            ("other", "Autre (nouveau client)"),
        ],
        initial="existing",
        required=True,
        widget=forms.Select(attrs={"class": "form-select"})
    )

    autre_nom = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Nom du client"
        })
    )

    autre_tel = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Téléphone"
        })
    )

    mode_paiement = forms.ChoiceField(
        choices=[

            ("cash", "Espèces (Cash)"),

            ("bankily", "Bankily"),
            ("masrvi", "Masrvi"),
            ("sadad", "Sadad"),
            ("bimbank", "BimBank"),
            ("moov_money", "Moov Money"),
            ("gaza_pay", "Gaza Pay"),
        ],

        required=True,
        widget=forms.Select(attrs={"class": "form-select"})
    )

    class Meta:
        model = Reservation
        fields = [
            "client_mode",
            "client",
            "autre_nom",
            "autre_tel",
            "voyage",
            "nb_sieges",
            "mode_paiement",
        ]
        widgets = {
            "client": forms.Select(attrs={"class": "form-select js-client-select"}),
            "voyage": forms.Select(attrs={"class": "form-select"}),
            "nb_sieges": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


        self.fields["client"].queryset = User.objects.filter(is_superuser=False).order_by("username")
        self.fields["client"].required = False
        self.fields["client"].empty_label = "— Sélectionner un client —"


        def client_label(u):
            fn = (u.first_name or "").strip()
            ln = (u.last_name or "").strip()
            name = (fn + " " + ln).strip()
            return f"{u.username} - {name}" if name else f"{u.username}"

        self.fields["client"].label_from_instance = client_label


        self.fields["voyage"].empty_label = "— Sélectionner un voyage —"
        self.fields["voyage"].queryset = self.get_open_voyages()

    def get_open_voyages(self):


        qs = Voyage.objects.select_related("vehicule", "trajet").order_by("date_depart", "heure_depart")

        allowed = []
        for v in qs:

            if hasattr(v, "check_statut"):
                if v.check_statut != "OUVERT":
                    continue


            if hasattr(v, "sieges_disponibles"):
                if int(v.sieges_disponibles) <= 0:
                    continue

            allowed.append(v.pk)

        return qs.filter(pk__in=allowed)

    def clean(self):
        cleaned = super().clean()

        mode = (cleaned.get("client_mode") or "").strip().lower()
        client = cleaned.get("client")
        autre_nom = (cleaned.get("autre_nom") or "").strip()
        autre_tel = (cleaned.get("autre_tel") or "").strip()

        voyage = cleaned.get("voyage")
        nb = cleaned.get("nb_sieges") or 1

        # ✅ Validation client
        if mode == "existing":
            if not client:
                self.add_error("client", "Veuillez sélectionner un client.")
        else:

            if not autre_nom:
                self.add_error("autre_nom", "Nom du client obligatoire.")
            if not autre_tel:
                self.add_error("autre_tel", "Téléphone obligatoire.")

            # ✅ Très important : Nous ne forçons pas le client à passer en mode Autre
            cleaned["client"] = None

        # ✅ Voyage de validation (doit être ouvert + avoir des places disponibles)
        if voyage:
            # Fermé ou complet
            if hasattr(voyage, "check_statut") and voyage.check_statut != "OUVERT":
                raise ValidationError("Ce voyage est fermé (complet ou délai < 30min).")

            if hasattr(voyage, "sieges_disponibles"):
                dispo = int(voyage.sieges_disponibles)
                if dispo <= 0:
                    self.add_error("voyage", "Voyage complet. Places restantes: 0")
                elif int(nb) > dispo:
                    self.add_error("nb_sieges", f"Il reste seulement {dispo} places disponibles.")

        return cleaned

