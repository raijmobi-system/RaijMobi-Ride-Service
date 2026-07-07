import jwt
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .models import UserClient

class KongJWTAuthentication(BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        
        # 🔍 DEBUG 1: Vendo se o cabeçalho chegou
        print(f"👉 [AUTH DEBUG] Cabeçalho Authorization: {auth_header}")
        
        if not auth_header or not auth_header.startswith('Bearer '):
            print("❌ [AUTH DEBUG] Cabeçalho ausente ou sem Bearer. Retornando None.")
            return None

        token = auth_header.split(' ')[1]

        try:
            payload = jwt.decode(token, options={"verify_signature": False})
            
            # 🔍 DEBUG 2: Vendo o conteúdo do Token
            print(f"👉 [AUTH DEBUG] Payload decodificado: {payload}")
            
            user_id = payload.get('user_id')
            
            if not user_id:
                print("❌ [AUTH DEBUG] user_id não encontrado no payload!")
                raise AuthenticationFailed('Token não contém a identificação do usuário.')

            # 🔍 DEBUG 3: Vendo quem o sistema está procurando
            print(f"👉 [AUTH DEBUG] Procurando usuário com ID: {user_id}")
            
            user = UserClient.objects.get(id=user_id)

            if user.is_suspended:
                raise AuthenticationFailed('Acesso negado. Usuário está suspenso temporariamente.')

            print("✅ [AUTH DEBUG] Autenticação concluída com sucesso!")
            return (user, token)

        except UserClient.DoesNotExist:
            print(f"❌ [AUTH DEBUG] Usuário {user_id} não existe no banco local do ride_service!")
            raise AuthenticationFailed('Usuário não encontrado na base de dados.')
        except jwt.DecodeError:
            print("❌ [AUTH DEBUG] Token mal formatado.")
            raise AuthenticationFailed('Token mal formatado.')

    def authenticate_header(self, request):
        return 'Bearer'