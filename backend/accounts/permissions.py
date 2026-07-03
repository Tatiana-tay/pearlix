from rest_framework.permissions import BasePermission


ADMIN_ROLE = "Admin"
STAFF_ROLE = "Staff"
DOCTOR_ROLE = "Doctor"
ACTIVE_STATUS = "Active"


def is_authenticated_user(user) -> bool:
    return bool(user and getattr(user, "is_authenticated", False))


def is_active_user(user) -> bool:
    return (
        is_authenticated_user(user)
        and bool(getattr(user, "is_active", False))
        and getattr(user, "status", None) == ACTIVE_STATUS
    )


def is_admin(user) -> bool:
    return is_active_user(user) and getattr(user, "role", None) == ADMIN_ROLE


def is_staff_role(user) -> bool:
    return is_active_user(user) and getattr(user, "role", None) == STAFF_ROLE


def is_doctor(user) -> bool:
    return is_active_user(user) and getattr(user, "role", None) == DOCTOR_ROLE


class IsActiveUser(BasePermission):
    def has_permission(self, request, view):
        return is_active_user(request.user)


class IsAdminRole(BasePermission):
    def has_permission(self, request, view):
        return is_admin(request.user)


class IsStaffRole(BasePermission):
    def has_permission(self, request, view):
        return is_staff_role(request.user)


class IsDoctorRole(BasePermission):
    def has_permission(self, request, view):
        return is_doctor(request.user)


class IsAdminOrStaff(BasePermission):
    def has_permission(self, request, view):
        return is_admin(request.user) or is_staff_role(request.user)


class IsStaffOrDoctor(BasePermission):
    def has_permission(self, request, view):
        return is_staff_role(request.user) or is_doctor(request.user)
