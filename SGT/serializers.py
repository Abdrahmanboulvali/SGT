from rest_framework import serializers
from .models import Vehicule, Chauffeur, Trajet, Voyage, Reservation, User


class TrajetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trajet
        fields = "__all__"


class VehiculeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicule
        fields = "__all__"


class ChauffeurSerializer(serializers.ModelSerializer):
    class Meta:
        model = Chauffeur
        fields = "__all__"


class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'telephone', 'role']


class VoyageSerializer(serializers.ModelSerializer):
    trajet_details = TrajetSerializer(source='trajet', read_only=True)
    vehicule_details = VehiculeSerializer(source='vehicule', read_only=True)
    chauffeur_details = ChauffeurSerializer(source='chauffeur', read_only=True)

    class Meta:
        model = Voyage
        fields = "__all__"


class ReservationSerializer(serializers.ModelSerializer):
    voyage_details = VoyageSerializer(source='voyage', read_only=True)
    client_details = ClientSerializer(source='client', read_only=True)

    class Meta:
        model = Reservation
        fields = "__all__"


# ✅✅✅ Serializer خاص بالموبايل: يعرض المقاعد المتاحة
class VoyageMobileSerializer(serializers.ModelSerializer):
    trajet = serializers.SerializerMethodField()
    prix = serializers.SerializerMethodField()
    sieges_disponibles = serializers.IntegerField(read_only=True)
    sieges_reserves = serializers.IntegerField(read_only=True)

    class Meta:
        model = Voyage
        fields = [
            "id_voyage",
            "date_depart",
            "heure_depart",
            "trajet",
            "prix",
            "prix_par_siege",
            "sieges_disponibles",
            "sieges_reserves",
        ]

    def get_trajet(self, obj):
        return str(obj.trajet)

    def get_prix(self, obj):
        try:
            return float(obj.prix_par_siege or 0)
        except Exception:
            return 0.0
