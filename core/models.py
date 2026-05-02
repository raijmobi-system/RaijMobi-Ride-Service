import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from .manager import SoftDeleteManager

# ==========================================
# 1. FUNÇÃO SENTINELA
# ==========================================
def get_sentinel_user_client():
    """Retorna ou cria o usuário fantasma para manter a integridade referencial."""
    sentinel_id = uuid.UUID(int=0)
    client, _ = UserClient.objects.get_or_create(
        id=sentinel_id,
        defaults={'nome': 'Deleted User Client'}
    )
    return client


# ==========================================
# 2. MIXINS ATÔMICOS (Nível Máximo de Quebra)
# ==========================================
class CreatedAtMixin(models.Model):
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True, editable=False)
    
    class Meta:
        abstract = True

class UpdatedAtMixin(models.Model):
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True, editable=False)
    
    class Meta:
        abstract = True

class CreatedByMixin(models.Model):
    created_by = models.ForeignKey(
        'UserClient', 
        verbose_name=_("Created by"),
        on_delete=models.SET(get_sentinel_user_client), 
        null=True,
        related_name="created_%(app_label)s_%(class)s_set",
    )
    
    class Meta:
        abstract = True

class UpdatedByMixin(models.Model):
    updated_by = models.ForeignKey(
        'UserClient', 
        verbose_name=_("Updated by"),
        on_delete=models.SET(get_sentinel_user_client), 
        null=True,
        related_name="updated_%(app_label)s_%(class)s_set",
    )
    
    class Meta:
        abstract = True


# ==========================================
# 3. MIXINS AGRUPADOS (Os "Blocos de Lego" Práticos)
# ==========================================
class TimeStampedModel(CreatedAtMixin, UpdatedAtMixin):
    """Agrupa o controle de tempo."""
    class Meta:
        abstract = True

class UserTrackedModel(CreatedByMixin, UpdatedByMixin):
    """Agrupa o controle de autoria."""
    class Meta:
        abstract = True


# ==========================================
# 4. OUTROS COMPORTAMENTOS BASE
# ==========================================
class UUIDModel(models.Model):
    # Gera um UUID automático para registros internos do Django
    uuid = models.UUIDField(unique=True, editable=False, default=uuid.uuid4)
    
    class Meta:
        abstract = True

class SoftDeleteModel(models.Model):
    is_deleted = models.BooleanField(default=False)
    objects = SoftDeleteManager()
    all_objects = models.Manager()  

    def delete(self, *args, **kwargs):
        self.is_deleted = True
        self.save()

    class Meta:
        abstract = True


# ==========================================
# 5. MODELOS CONCRETOS E BASE FINAIS
# ==========================================

class UserClient(TimeStampedModel):
    """
    O cliente que vem do Supabase. 
    Usa apenas os timestamps (TimeStampedModel). Não herda autoria nem UUIDModel, 
    pois o ID dele é a própria chave primária definida externamente.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=255)

    def __str__(self):
        return self.nome


class BaseModel(UUIDModel, TimeStampedModel, UserTrackedModel):
    """
    Modelo padrão completo para entidades de negócio (ex: Carona, Veículo).
    """
    class Meta:
        abstract = True


class BaseModelWithSoftDelete(BaseModel, SoftDeleteModel):
    """
    Modelo padrão com suporte a lixeira (Soft Delete) para dados sensíveis ou históricos.
    """
    class Meta:      
        abstract = True