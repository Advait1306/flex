from tortoise import fields
from tortoise.models import Model


class User(Model):
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=255, unique=True)
    password_hash = fields.CharField(max_length=255)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "users"


class FreewriteDocument(Model):
    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField("models.User", related_name="freewrite_docs", unique=True)
    content = fields.JSONField(default=[])
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "freewrite_documents"
