from django.db import models
from django.conf import settings
from beneficiaries.models import Beneficiary
import uuid


class StipendEvent(models.Model):
    """
    Represents a stipend distribution schedule (e.g., monthly payout).
    Claims can be linked to a StipendEvent so logs show which payout period
    is being claimed.

    event_type:
      REGULAR      — standard monthly stipend; all active beneficiaries are eligible.
      BIRTHDAY_BONUS — birthday bonus; only beneficiaries whose birth month matches
                       the event month are eligible.
    """
    EVENT_TYPE_REGULAR = 'regular'
    EVENT_TYPE_BIRTHDAY = 'birthday_bonus'
    EVENT_TYPE_CHOICES = [
        (EVENT_TYPE_REGULAR, 'Regular Monthly Stipend'),
        (EVENT_TYPE_BIRTHDAY, 'Birthday Bonus'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    date = models.DateField()
    event_type = models.CharField(
        max_length=30,
        choices=EVENT_TYPE_CHOICES,
        default=EVENT_TYPE_REGULAR,
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_stipend_events',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'fans_stipend_events'
        ordering = ['date']

    def __str__(self):
        return f'{self.title} ({self.date})'

    def is_beneficiary_eligible(self, beneficiary) -> bool:
        """
        Returns True if the beneficiary is eligible for this stipend event.
        For BIRTHDAY_BONUS events, the beneficiary's birth month must match the event month.
        """
        if self.event_type == self.EVENT_TYPE_BIRTHDAY:
            return beneficiary.date_of_birth.month == self.date.month
        return True

    def get_eligible_beneficiaries(self):
        """Returns a queryset of active beneficiaries eligible for this event."""
        from beneficiaries.models import Beneficiary
        qs = Beneficiary.objects.filter(
            status=Beneficiary.STATUS_ACTIVE,
            consent_given=True,
        )
        if self.event_type == self.EVENT_TYPE_BIRTHDAY:
            qs = qs.filter(date_of_birth__month=self.date.month)
        return qs


class FaceEmbedding(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    beneficiary = models.OneToOneField(
        Beneficiary,
        on_delete=models.CASCADE,
        related_name='face_embedding'
    )
    embedding_data = models.BinaryField()
    embedding_version = models.CharField(max_length=20, default='facenet-v1')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )

    class Meta:
        db_table = 'fans_face_embeddings'

    def __str__(self):
        return f'Embedding for {self.beneficiary.full_name}'


class VerificationAttempt(models.Model):
    DECISION_VERIFIED = 'verified'
    DECISION_NOT_VERIFIED = 'not_verified'
    DECISION_MANUAL_REVIEW = 'manual_review'
    DECISION_DENIED = 'denied'
    DECISION_CHOICES = [
        (DECISION_VERIFIED, 'Verified'),
        (DECISION_NOT_VERIFIED, 'Not Verified'),
        (DECISION_MANUAL_REVIEW, 'Manual Review'),
        (DECISION_DENIED, 'Denied'),
    ]

    CLAIMANT_BENEFICIARY = 'beneficiary'
    CLAIMANT_REPRESENTATIVE = 'representative'
    CLAIMANT_CHOICES = [
        (CLAIMANT_BENEFICIARY, 'Beneficiary'),
        (CLAIMANT_REPRESENTATIVE, 'Authorized Representative'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    beneficiary = models.ForeignKey(
        Beneficiary,
        on_delete=models.CASCADE,
        related_name='verification_attempts'
    )
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='performed_verifications'
    )

    # Linked stipend event (which payout period is being claimed)
    stipend_event = models.ForeignKey(
        StipendEvent,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='claims',
    )

    # Who is claiming
    claimant_type = models.CharField(
        max_length=20,
        choices=CLAIMANT_CHOICES,
        default=CLAIMANT_BENEFICIARY,
    )

    # Liveness result
    liveness_passed = models.BooleanField(null=True)
    liveness_score = models.FloatField(null=True, blank=True)
    anti_spoof_score = models.FloatField(null=True, blank=True)
    head_movement_completed = models.BooleanField(default=False)

    # Face matching
    similarity_score = models.FloatField(null=True, blank=True)
    threshold_used = models.FloatField(default=0.60)
    decision = models.CharField(max_length=20, choices=DECISION_CHOICES, null=True, blank=True)
    decision_reason = models.CharField(max_length=500, blank=True)

    # Image quality at verification time
    face_quality_score = models.FloatField(null=True, blank=True)

    # Retry tracking
    attempt_number = models.PositiveSmallIntegerField(default=1)
    session_id = models.UUIDField(default=uuid.uuid4)

    # Fallback
    fallback_triggered = models.BooleanField(default=False)
    fallback_id_verified = models.BooleanField(null=True)
    fallback_id_type = models.CharField(max_length=50, blank=True)

    # Override
    overridden = models.BooleanField(default=False)
    override_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='overridden_verifications'
    )
    override_reason = models.TextField(blank=True)
    override_at = models.DateTimeField(null=True, blank=True)

    timestamp = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = 'fans_verification_attempts'
        ordering = ['-timestamp']

    def __str__(self):
        return f'{self.beneficiary.full_name} - {self.decision} @ {self.timestamp}'


class SystemConfig(models.Model):
    key = models.CharField(max_length=100, unique=True)
    value = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'fans_system_config'

    def __str__(self):
        return f'{self.key} = {self.value}'

    @classmethod
    def get_threshold(cls):
        """
        Returns the active verification threshold.
        In DEMO_MODE, the DB value defaults to DEMO_THRESHOLD if not explicitly set.
        """
        from django.conf import settings as django_settings
        demo_mode = getattr(django_settings, 'DEMO_MODE', True)
        fallback = (
            getattr(django_settings, 'DEMO_THRESHOLD', 0.60) if demo_mode
            else getattr(django_settings, 'VERIFICATION_THRESHOLD', 0.75)
        )
        try:
            return float(cls.objects.get(key='verification_threshold').value)
        except cls.DoesNotExist:
            return fallback
