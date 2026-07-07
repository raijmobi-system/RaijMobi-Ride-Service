from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from core.models import UserClient # Seu model de usuário
import base64
import json

class KongHeaderAuthentication(BaseAuthentication):
    def authenticate(self, request):
        # O Kong JWT plugin, por padrão, envia as claims do token neste header
        # formato base64. Ou envia headers customizados dependendo da sua config.
        # Vamos assumir que você configurou o Kong para injetar um header com o ID do usuário:
        # HTTP_X_USER_ID (o Django adiciona HTTP_ antes de headers customizados)
        
        user_id = request.META.get('HTTP_X_USER_ID') 

        if not user_id:
            # Se não tem o header, a requisição não passou pelo Kong ou é uma rota pública
            return None 

        try:
            # Verifica se o usuário de fato existe no banco do microserviço
            user = UserClient.objects.get(id=user_id)
            
            if user.is_suspended:
                 raise AuthenticationFailed('Usuário suspenso.')
                 
            return (user, None) # Autenticado com sucesso!
            
        except UserClient.DoesNotExist:
            raise AuthenticationFailed('Usuário não encontrado no banco de dados.')