# from rest_framework import viewsets
# from .models import Vehicule, Chauffeur, Trajet, Voyage, Reservation, User
# from .serializers import (
#     VehiculeSerializer, ChauffeurSerializer, TrajetSerializer,
#     VoyageSerializer, ReservationSerializer, ClientSerializer
# )
#
# # نستخدم ModelViewSet لأنه يوفر كل شيء جاهزاً (قراءة، إضافة، تعديل، حذف)
# # وهذا ما يطلبه الدرس في Module 8
#
# class VehiculeViewSet(viewsets.ModelViewSet):
#     queryset = Vehicule.objects.all()
#     serializer_class = VehiculeSerializer
#
# class ChauffeurViewSet(viewsets.ModelViewSet):
#     queryset = Chauffeur.objects.all()
#     serializer_class = ChauffeurSerializer
#
# class TrajetViewSet(viewsets.ModelViewSet):
#     queryset = Trajet.objects.all()
#     serializer_class = TrajetSerializer
#
# class VoyageViewSet(viewsets.ModelViewSet):
#     # ترتيب الرحلات حسب التاريخ الأحدث
#     queryset = Voyage.objects.all().order_by('-date_depart')
#     serializer_class = VoyageSerializer
#
# class ReservationViewSet(viewsets.ModelViewSet):
#     queryset = Reservation.objects.all().order_by('-date_reservation')
#     serializer_class = ReservationSerializer
#
# class ClientViewSet(viewsets.ModelViewSet):
#     queryset = User.objects.filter(role='CLIENT')
#     serializer_class = ClientSerializer