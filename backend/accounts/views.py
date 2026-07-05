from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from .serializers import LoginSerializer, UserSerializer


User = get_user_model()


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        return Response(
            {
                "access": access_token,
                "refresh": refresh_token,
                "accessToken": access_token,
                "refreshToken": refresh_token,
                "user": UserSerializer(user).data,
                "mustChangePassword": user.must_change_password,
            }
        )


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.status != User.Status.ACTIVE:
            return Response(
                {"detail": "Inactive users cannot authenticate."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(UserSerializer(request.user).data)


class RolesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"roles": [choice.value for choice in User.Role]})


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        return Response(
            {
                "ok": True,
                "detail": "Logout is client-side in Phase 0B; discard access and refresh tokens.",
            }
        )


class RefreshView(TokenRefreshView):
    pass
