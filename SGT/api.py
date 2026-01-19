from django.http import JsonResponse
from rest_framework.authtoken.models import Token


def api_ping(request):
    return JsonResponse({"ok": True, "message": "SGT API is working"})

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate
import json

@csrf_exempt
def api_login(request):
    if request.method == "POST":
        data = json.loads(request.body)
        username = data.get("username")
        password = data.get("password")

        user = authenticate(username=username, password=password)
        if user:
            return JsonResponse({
                "ok": True,
                "user": {
                    "id": user.id,
                    "username": user.username
                }
            })
        else:
            return JsonResponse({
                "ok": False,
                "error": "Identifiants invalides"
            }, status=401)
