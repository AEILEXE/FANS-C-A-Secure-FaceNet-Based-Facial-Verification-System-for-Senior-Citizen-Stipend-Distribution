from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    # ── Role constants ────────────────────────────────────────────────────────
    # ROLE_ADMIN (legacy)  — DB value 'admin'; no longer assigned to new users.
    #                        Migration 0006 converted all existing rows to
    #                        admin_it. Kept as a constant so is_admin_it remains
    #                        a safe fallback for any row that somehow still
    #                        carries the old value (e.g. restored from backup).
    # ROLE_HEAD_BRGY       — Operational admin (Head Barangay / Barangay Captain).
    #                        Non-technical. Sees dashboards, reports, user mgmt.
    #                        Does NOT see LAN IPs, connection diagnostics, or
    #                        system-setup pages.
    # ROLE_ADMIN_IT        — Technical administrator (IT/Admin).
    #                        Full access: everything Head Barangay sees plus
    #                        System Connection Info, diagnostics, network setup.
    # ROLE_STAFF           — Operational user. Register, verify, workflow only.
    #                        No user management or system diagnostics.
    ROLE_ADMIN    = 'admin'      # legacy constant — no new users assigned this value
    ROLE_HEAD_BRGY = 'head_brgy' # operational admin (non-technical)
    ROLE_ADMIN_IT  = 'admin_it'  # technical administrator
    ROLE_STAFF    = 'staff'

    ROLE_CHOICES = [
        (ROLE_HEAD_BRGY, 'Head Barangay'),
        (ROLE_ADMIN_IT,  'IT / Admin'),
        (ROLE_STAFF,     'Staff'),
    ]

    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=ROLE_STAFF)
    employee_id = models.CharField(max_length=50, unique=True, null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    profile_picture = models.ImageField(upload_to='users/profile_pics/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'fans_users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    # ── Role helpers ──────────────────────────────────────────────────────────

    @property
    def is_admin(self):
        """True for all management-level roles (Head Barangay + IT Admin + legacy admin).
        Use this for checks that both operational and technical admins should pass."""
        return self.role in (self.ROLE_ADMIN, self.ROLE_ADMIN_IT, self.ROLE_HEAD_BRGY)

    @property
    def is_admin_it(self):
        """True only for IT/Admin and legacy admin roles.

        Permission is determined exclusively by the ``role`` field.
        Django's ``is_superuser`` flag does NOT grant app-level IT admin
        access — it only controls Django's built-in /admin/ panel, which
        is entirely separate from this application's role system.

        Use this to gate system diagnostics, connection info, and network
        pages that Head Barangay and Staff must never see.
        """
        return self.role in (self.ROLE_ADMIN, self.ROLE_ADMIN_IT)

    @property
    def is_head_barangay(self):
        """True only for the Head Barangay operational-admin role."""
        return self.role == self.ROLE_HEAD_BRGY

    @property
    def is_staff_member(self):
        return self.role == self.ROLE_STAFF

    def __str__(self):
        return f'{self.get_full_name()} ({self.role})'
