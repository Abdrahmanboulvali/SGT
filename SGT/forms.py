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

class ReservationForm(forms.ModelForm):
    preuve_paiement = forms.ImageField(
        required=False,
        label="Capture d'écran du paiement",
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'})
    )

    class Meta:
        model = Reservation
        fields = ['client', 'voyage', 'nb_sieges', 'statut', 'preuve_paiement']
        widgets = {
            'client': forms.Select(attrs={'class': 'form-select'}),
            'voyage': forms.Select(attrs={'class': 'form-select'}),
            'nb_sieges': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'statut': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super(ReservationForm, self).__init__(*args, **kwargs)
        self.fields['statut'].required = False
        today = timezone.now().date()
        self.fields['voyage'].queryset = Voyage.objects.filter(
            date_depart__gte=today
        ).order_by('date_depart', 'heure_depart')
        self.fields['client'].empty_label = "Sélectionnez un client..."
        self.fields['voyage'].empty_label = "Sélectionnez un voyage..."