from rest_framework.permissions import BasePermission


class IsCustomer(BasePermission):

    def has_permission(self,request,view):
        return (
            request.user.is_authenticated
            and not request.user.is_vendor
        )


class IsVendor(BasePermission):

    def has_permission(self,request,view):
        return (
            request.user.is_authenticated
            and request.user.is_vendor
        )


class IsApprovedVendor(BasePermission):

    def has_permission(self,request,view):

        if not request.user.is_authenticated:
            return False

        if not request.user.is_vendor:
            return False

        try:
            return request.user.vendorprofile.is_approved
        except:
            return False


class IsAdminUser(BasePermission):

    def has_permission(self,request,view):
        return (
            request.user.is_authenticated
            and request.user.is_admin
        )