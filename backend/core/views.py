from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsActiveUser, IsAdminRole

from .models import ClinicSettings
from .serializers import ClinicSettingsSerializer


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    return Response({"status": "ok"})


class ClinicSettingsView(APIView):
    def get_permissions(self):
        if self.request.method == "PATCH":
            return [IsAdminRole()]
        return [IsActiveUser()]

    def get(self, request):
        settings = ClinicSettings.get_solo()
        return Response(ClinicSettingsSerializer(settings).data)

    def patch(self, request):
        settings = ClinicSettings.get_solo()
        serializer = ClinicSettingsSerializer(
            settings,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
