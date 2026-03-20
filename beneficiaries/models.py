from django.db import models
from django.conf import settings
import uuid


class Beneficiary(models.Model):
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
    def is_eligible_to_claim(self):
        """Only active beneficiaries with consent can claim."""
        return self.status == self.STATUS_ACTIVE and self.consent_given

    def save(self, *args, **kwargs):
        if not self.beneficiary_id:
            import datetime
            year = datetime.date.today().year
            count = Beneficiary.objects.filter(
                beneficiary_id__startswith=f'BEN-{year}-'
            ).count() + 1
            self.beneficiary_id = f'BEN-{year}-{count:05d}'
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.full_name} ({self.beneficiary_id})'
