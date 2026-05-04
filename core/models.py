import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from .manager import SoftDeleteManager


# ==========================================
# 1. FUNÇÃO SENTINELA (CORRIGIDA)
# ==========================================
def get_sentinel_user_client():
    from core.models import UserClient  # IMPORT INTERNO (evita circular import)

    sentinel_id = uuid.UUID(int=0)
    client, _ = UserClient.objects.get_or_create(
        id=sentinel_id,
        defaults={'nome': 'Deleted User Client'}
    )
    return client


# ==========================================
# 2. MIXINS ATÔMICOS
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
        'core.UserClient',   # ✅ CORRIGIDO
        verbose_name=_("Created by"),
        on_delete=models.SET(get_sentinel_user_client),
        null=True,
        related_name="created_%(app_label)s_%(class)s_set",
    )

    class Meta:
        abstract = True


class UpdatedByMixin(models.Model):
    updated_by = models.ForeignKey(
        'core.UserClient',   # ✅ CORRIGIDO
        verbose_name=_("Updated by"),
        on_delete=models.SET(get_sentinel_user_client),
        null=True,
        related_name="updated_%(app_label)s_%(class)s_set",
    )

    class Meta:
        abstract = True


# ==========================================
# 3. MIXINS AGRUPADOS
# ==========================================
class TimeStampedModel(CreatedAtMixin, UpdatedAtMixin):
    class Meta:
        abstract = True


class UserTrackedModel(CreatedByMixin, UpdatedByMixin):
    class Meta:
        abstract = True


# ==========================================
# 4. BASES GENÉRICAS
# ==========================================
class UUIDModel(models.Model):
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
# 5. MODELO USUARIO (BASE DO SISTEMA)
# ==========================================
class UserClient(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=255)

    def __str__(self):
        return self.nome


# ==========================================
# 6. MODELOS BASE
# ==========================================
class BaseModel(UUIDModel, TimeStampedModel, UserTrackedModel):
    class Meta:
        abstract = True


class BaseModelWithSoftDelete(BaseModel, SoftDeleteModel):
    class Meta:
        abstract = True