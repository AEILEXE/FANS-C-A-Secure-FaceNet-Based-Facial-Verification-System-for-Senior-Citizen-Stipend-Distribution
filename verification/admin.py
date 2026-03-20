from django.contrib import admin
from .models import FaceEmbedding, VerificationAttempt, SystemConfig


@admin.register(FaceEmbedding)
class FaceEmbeddingAdmin(admin.ModelAdmin):
    list_display = ['beneficiary', 'embedding_version', 'created_at']
    readonly_fields = ['embedding_data', 'created_at', 'updated_at']


@admin.register(VerificationAttempt)
class VerificationAttemptAdmin(admin.ModelAdmin):
    list_display = ['beneficiary', 'decision', 'similarity_score', 'liveness_passed', 'timestamp']
    list_filter = ['decision', 'liveness_passed', 'overridden']
    readonly_fields = ['id', 'timestamp']


@admin.register(SystemConfig)
class SystemConfigAdmin(admin.ModelAdmin):
    list_display = ['key', 'value', 'updated_at']
