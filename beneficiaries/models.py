"""
Beneficiary data models for FANS-C.

Beneficiary        — core record for each senior citizen; includes personal info,
                     address, status, consent flag, and offline-sync tracking fields.
Representative     — authorised representative who may claim on behalf of a beneficiary.
                     Representatives have their own face embedding for biometric verification.

Offline-sync fields (is_synced, sync_error, last_synced_at) are managed by
beneficiaries/sync.py and the `sync_beneficiaries` management command. See those files
for the full offline-first sync architecture.
"""
from django.db import models
from django.conf import settings
import uuid


class Beneficiary(models.Model):
    """
    Core record for a senior citizen enrolled in the Quezon City stipend programme.

    Status lifecycle:
      pending  → active  (after registration review and face enrollment)
      active   → inactive (suspended by admin)
      active   → deceased (recorded upon notification)

    is_eligible_to_claim returns True only for STATUS_ACTIVE beneficiaries with consent.
    Only active beneficiaries appear in verification search results.
    """
    STATUS_ACTIVE = 'active'
    STATUS_INACTIVE = 'inactive'
    STATUS_DECEASED = 'deceased'
    STATUS_PENDING = 'pending'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_INACTIVE, 'Inactive'),
        (STATUS_DECEASED, 'Deceased'),
        (STATUS_PENDING, 'Pending'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    beneficiary_id = models.CharField(max_length=20, unique=True)

    # Personal info
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=10, choices=[('M', 'Male'), ('F', 'Female'), ('O', 'Other')])
    address = models.TextField()
    barangay = models.CharField(max_length=100)
    municipality = models.CharField(max_length=100)
    province = models.CharField(max_length=100)
    contact_number = models.CharField(max_length=20, blank=True)

    # Government ID
    senior_citizen_id = models.CharField(max_length=50, blank=True, verbose_name='Senior Citizen ID Number')
    valid_id_type = models.CharField(max_length=50, blank=True, verbose_name='Valid ID Type')
    valid_id_number = models.CharField(max_length=50, blank=True, verbose_name='Valid ID Number')

    # Representative info (authorized to claim on behalf)
    has_representative = models.BooleanField(default=False)
    rep_first_name = models.CharField(max_length=100, blank=True)
    rep_last_name = models.CharField(max_length=100, blank=True)
    rep_relationship = models.CharField(max_length=100, blank=True)
    rep_contact = models.CharField(max_length=20, blank=True)
    rep_id_type = models.CharField(max_length=50, blank=True)
    rep_id_number = models.CharField(max_length=50, blank=True)

    # Consent
    consent_given = models.BooleanField(default=False)
    consent_date = models.DateTimeField(null=True, blank=True)

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)

    # Lifecycle deactivation tracking
    deactivated_at = models.DateTimeField(null=True, blank=True)
    deactivated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='deactivated_beneficiaries',
    )
    deactivated_reason = models.TextField(blank=True)

    # Offline-first sync tracking
    # False = record created locally and not yet sent to the central server.
    # True  = record has been successfully synced to the central API.
    # This field is managed by beneficiaries/sync.py and the sync_beneficiaries command.
    is_synced = models.BooleanField(
        default=False,
        db_index=True,
        help_text='True when this record has been synced to the central server.',
    )
    sync_error = models.TextField(
        blank=True,
        help_text='Last sync error message, if any. Cleared on successful sync.',
    )
    last_synced_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Timestamp of the last successful sync to the central server.',
    )

    profile_picture = models.ImageField(
        upload_to='beneficiaries/profile_pics/',
        null=True,
        blank=True,
        help_text='Optional profile photo for identification.',
    )

    registered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='registered_beneficiaries'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'fans_beneficiaries'
        ordering = ['last_name', 'first_name']

    @property
    def full_name(self):
        parts = [self.first_name, self.middle_name, self.last_name]
        return ' '.join(p for p in parts if p)

    @property
    def rep_full_name(self):
        """Full name of the authorized representative, or empty string."""
        parts = [self.rep_first_name, self.rep_last_name]
        return ' '.join(p for p in parts if p)

    @property
    def age(self):
        """Age in years as of today."""
        import datetime
        today = datetime.date.today()
        dob = self.date_of_birth
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    @property
    def is_senior_citizen(self):
        """True if the beneficiary is 60 years old or older."""
        return self.age >= 60

    @property
    def is_eligible_to_claim(self):
        """
        Only active beneficiaries who have given consent may claim.
        Inactive, deceased, and pending beneficiaries are blocked.
        """
        return (
            self.status == self.STATUS_ACTIVE
            and self.consent_given
        )

    def is_eligible_for_event(self, stipend_event) -> bool:
        """
        Check if this beneficiary is eligible for the given stipend event.
        Combines lifecycle eligibility and event-specific rules.
        """
        if not self.is_eligible_to_claim:
            return False
        return stipend_event.is_beneficiary_eligible(self)

    def save(self, *args, **kwargs):
        if not self.beneficiary_id:
            import datetime
            year = datetime.date.today().year
            # Use select_for_update to avoid ID collision in concurrent requests
            last = (
                Beneficiary.objects.filter(
                    beneficiary_id__startswith=f'BEN-{year}-'
                )
                .order_by('-beneficiary_id')
                .values_list('beneficiary_id', flat=True)
                .first()
            )
            if last:
                try:
                    last_num = int(last.split('-')[-1])
                except (ValueError, IndexError):
                    last_num = 0
            else:
                last_num = 0
            self.beneficiary_id = f'BEN-{year}-{last_num + 1:05d}'
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.full_name} ({self.beneficiary_id})'


class Representative(models.Model):
    """
    A biometrically-registered representative authorized to claim on behalf of a beneficiary.
    Each representative must have face data captured before they can be used in verification.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    beneficiary = models.ForeignKey(
        Beneficiary,
        on_delete=models.CASCADE,
        related_name='representatives',
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    relationship = models.CharField(max_length=100)
    contact_number = models.CharField(max_length=20)
    valid_id_type = models.CharField(max_length=50)
    valid_id_number = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)
    registered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='registered_representatives',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'fans_representatives'
        ordering = ['last_name', 'first_name']

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'.strip()

    @property
    def has_face_data(self):
        return hasattr(self, 'face_embedding')

    def __str__(self):
        return f'{self.full_name} (Rep for {self.beneficiary.beneficiary_id})'
