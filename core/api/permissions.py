from rest_framework.permissions import BasePermission

class IsDriver(BasePermission):

    message = "Apenas motoristas podem realizar essa ação."

    def has_permission(self, request, view):
       user_id = request.data.get("user")

       if not user_id:
           return True
       
       from core.models import UserClient

       try:
           user = UserClient.objects.get(id=user_id)
           return user.is_driver
       except UserClient.DoesNotExist:
           return False

class IsPassenger(BasePermission):

    message = "Apenas passageiros podem realizar esta ação."

    def has_permission(self, request, view):
        passenger_id = request.data.get("passenger")

        if not passenger_id:
            return True
        
        from core.models import UserClient

        try:
            user = UserClient.objects.get(id=passenger_id)
            return not user.is_driver
        except UserClient.DoesNotExist:
            return False