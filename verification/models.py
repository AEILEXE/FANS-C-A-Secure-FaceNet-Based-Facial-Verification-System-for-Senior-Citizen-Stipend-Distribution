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
      REGULAR        — standard monthly stipend; all active beneficiaries are eligible.
      BIRTHDAY_BONUS — birthday bonus; only beneficiaries whose birth month matches
                       the event month are eligible.

    Payout window:
      payout_start_date / payout_end_date define the date range during which
      beneficiaries may claim for this event. If these are not set, only the exact
      `date` is matched (single-day event).
    """
    EVENT_TYPE_REGULAR = 'regular'
    EVENT_TYPE_BIRTHDAY = 'birthday_bonus'
    EVENT_TYPE_CHOICES = [
        (EVENT_TYPE_REGULAR, 'Regular Monthly Stipend'),
        (EVENT_TYPE_BIRTHDAY, 'Birthday Bonus'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    date = models.DateField(help_text='Main payout date or start of payout period.')
    event_type = models.CharField(
        max_length=30,
        choices=EVENT_TYPE_CHOICES,
        default=EVENT_TYPE_REGULAR,
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    # Optional payout window — if set, claims are accepted within start..end inclusive
    payout_start_date = models.DateField(
        null=True, blank=True,
        help_text='First day beneficiaries may claim. Defaults to date if not set.',
    )
    payout_end_date = models.DateField(
        null=True, blank=True,
        help_text='Last day beneficiaries may claim. Defaults to date if not set.',
    )

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

    def get_claim_start(self):
        """First day this event accepts claims."""
        return self.payout_start_date or self.date

    def get_claim_end(self):
        """Last day this event accepts claims."""
        return self.payout_end_date or self.date

    def is_active_on_date(self, check_date) -> bool:
        """
        Returns True if check_date falls within the payout window for this event.
        Also checks is_active flag.
        """
        if not self.is_active:
            return False
        return self.get_claim_start() <= check_date <= self.get_claim_end()

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

    @classmethod
    def get_active_event_for_date(cls, check_date):
        """
        Returns the active StipendEvent whose payout window contains check_date,
        or None if no such event exists.

        Priority: events whose payout_start_date <= today <= payout_end_date.
        Falls back to events where date == today (legacy single-day events).
        """
        # Events with an explicit payout window containing check_date
        windowed = cls.objects.filter(
            is_active=True,
            payout_start_date__lte=check_date,
            payout_end_date__gte=check_date,
        ).order_by('date').first()
        if windowed:
            return windowed

        # Fallback: single-day events matching exactly
        return cls.objects.filter(
            is_active=True,
            date=check_date,
            payout_start_date__isnull=True,
        ).order_by('date').first()


class FaceEmbedding(models.Model):
    """
    Primary face embedding for a beneficiary (FaceNet, 128-d, encrypted).
    One per beneficiary. For additional templates, see the registration re-enroll flow.
    """
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

    # Template debug info (which stored template matched, how many were checked)
    matched_template = models.CharField(max_length=30, blank=True)
    templates_checked = models.PositiveSmallIntegerField(default=0)

    # Image quality at verification time
    face_quality_score = models.FloatField(null=True, blank=True)
    face_quality_ok = models.BooleanField(null=True, blank=True)

    # Retry tracking
    attempt_number = models.PositiveSmallIntegerField(default=1)
    session_id = models.UUIDField(default=uuid.uuid4)

    # Demo mode flag — clarifies in audit logs whether threshold was relaxed
    demo_mode_active = models.BooleanField(
        default=False,
        help_text='True if DEMO_MODE was enabled at the time of this verification.'
    )

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


class AdditionalFaceEmbedding(models.Model):
    """
    Extra face templates for multi-shot matching.
    Added via the "Update Face Data" workflow when appearance changes or original
    registration quality was poor.  compare_with_all_embeddings() picks the BEST
    score across primary + all additional templates.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    beneficiary = models.ForeignKey(
        Beneficiary,
        on_delete=models.CASCADE,
        related_name='additional_embeddings',
    )
    embedding_data = models.BinaryField()
    embedding_version = models.CharField(max_length=20, default='facenet-v1')
    label = models.CharField(
        max_length=100, blank=True,
        help_text='Free-text label e.g. "update-2025-03"',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_additional_embeddings',
    )

    class Meta:
        db_table = 'fans_additional_face_embeddings'
        ordering = ['-created_at']

    def __str__(self):
        return f'Extra template for {self.beneficiary.full_name} ({self.created_at.date()})'


class FaceUpdateLog(models.Model):
    """
    Audit trail for every face re-enrollment event.
    Captures who triggered it, why, and whether it succeeded.
    """
    REASON_REPEATED_FAILURE  = 'repeated_failure'
    REASON_APPEARANCE_CHANGE = 'appearance_change'
    REASON_POOR_ORIGINAL     = 'poor_original'
    REASON_STAFF_DECISION    = 'staff_decision'
    REASON_CHOICES = [
        (REASON_REPEATED_FAILURE,  'Repeated Verification Failure'),
        (REASON_APPEARANCE_CHANGE, 'Major Appearance Change'),
        (REASON_POOR_ORIGINAL,     'Poor Original Registration'),
        (REASON_STAFF_DECISION,    'Staff Decision / Other'),
    ]

    ACTION_REPLACE  = 'replace'   # Replace primary embedding
    ACTION_AUGMENT  = 'augment'   # Add as additional template only
    ACTION_CHOICES = [
        (ACTION_REPLACE, 'Replace Primary Embedding'),
        (ACTION_AUGMENT, 'Add as Additional Template'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    beneficiary = models.ForeignKey(
        Beneficiary,
        on_delete=models.CASCADE,
        related_name='face_update_logs',
    )
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='face_updates_performed',
    )
    reason = models.CharField(max_length=30, choices=REASON_CHOICES)
    action = models.CharField(
        max_length=10,
        choices=ACTION_CHOICES,
        default=ACTION_REPLACE,
    )
    notes = models.TextField(blank=True)
    success = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'fans_face_update_logs'
        ordering = ['-timestamp']

    def __str__(self):
        status = 'OK' if self.success else 'FAILED'
        return (
            f'Face update [{status}] for {self.beneficiary.full_name} '
            f'by {self.performed_by} ({self.timestamp.date()})'
        )


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
        Production mode defaults to VERIFICATION_THRESHOLD (0.75).
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
