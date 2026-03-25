"""
Offline-First Sync Service for FANS-C.

Purpose
-------
This module enables the system to operate completely offline (no network
required) and then push locally-registered beneficiary records to a
central server once an internet connection is available.

How it works
------------
1. Every new Beneficiary is saved with is_synced=False.
2. When connectivity is detected (or manually triggered), sync_all() sends
   unsynced records to the SYNC_API_URL endpoint defined in settings.
3. On HTTP 200/201 the record is marked is_synced=True and last_synced_at
   is set to the current timestamp.
4. On failure the error is logged and stored in sync_error; the record
   remains is_synced=False and will be retried on the next sync run.

Configuration (.env)
--------------------
SYNC_API_URL   — Base URL of the central API, e.g. https://central.fans-c.gov.ph/api
SYNC_API_KEY   — Bearer token / API key for the central server (keep secret).
SYNC_TIMEOUT   — HTTP request timeout in seconds (default 30).
SYNC_BATCH_SIZE— Maximum records per sync run (default 50).

Key sharing
-----------
The EMBEDDING_ENCRYPTION_KEY used locally MUST be identical on the central
server. The encrypted embedding bytes are transferred as-is; the central
server decrypts them using the same Fernet key. If the keys differ, face
data will be unreadable on the other side.

Conflict handling
-----------------
Records are identified by their UUID primary key (id) and by beneficiary_id.
The central API is expected to treat a duplicate UUID as an upsert (update
existing) rather than an error. This prevents duplicates when a record is
re-sent after a partial failure.

Usage
-----
    from beneficiaries.sync import sync_all, is_online

    if is_online():
        result = sync_all()
        print(result)  # {'synced': 5, 'failed': 0, 'skipped': 0}

    # Or run from the command line:
    #   python manage.py sync_beneficiaries
"""
import logging
import socket
from datetime import datetime, timezone as dt_timezone

logger = logging.getLogger('beneficiaries.sync')

# ── Connectivity check ─────────────────────────────────────────────────────


def is_online(host: str = '8.8.8.8', port: int = 53, timeout: float = 3.0) -> bool:
    """
    Return True if the machine can reach the internet.

    Uses a raw TCP connect to a well-known host (Google DNS by default).
    No DNS query is made, so this works even when DNS is broken.
    """
    try:
        socket.setdefaulttimeout(timeout)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((host, port))
        return True
    except OSError:
        return False


# ── Payload builder ────────────────────────────────────────────────────────

def _build_payload(beneficiary) -> dict:
    """
    Serialise a Beneficiary record into a JSON-safe dict for the central API.

    Encrypted embedding data is base64-encoded so it survives JSON transport.
    """
    import base64

    payload = {
        'id': str(beneficiary.id),
        'beneficiary_id': beneficiary.beneficiary_id,
        'first_name': beneficiary.first_name,
        'middle_name': beneficiary.middle_name,
        'last_name': beneficiary.last_name,
        'date_of_birth': beneficiary.date_of_birth.isoformat(),
        'gender': beneficiary.gender,
        'address': beneficiary.address,
        'barangay': beneficiary.barangay,
        'municipality': beneficiary.municipality,
        'province': beneficiary.province,
        'contact_number': beneficiary.contact_number,
        'senior_citizen_id': beneficiary.senior_citizen_id,
        'valid_id_type': beneficiary.valid_id_type,
        'valid_id_number': beneficiary.valid_id_number,
        'status': beneficiary.status,
        'consent_given': beneficiary.consent_given,
        'has_representative': beneficiary.has_representative,
        'created_at': beneficiary.created_at.isoformat(),
        'updated_at': beneficiary.updated_at.isoformat(),
        # Face embedding — bytes are base64-encoded for JSON transport
        'face_embedding': None,
    }

    try:
        embedding_obj = beneficiary.face_embedding
        raw_bytes = bytes(embedding_obj.embedding_data)
        payload['face_embedding'] = {
            'data_b64': base64.b64encode(raw_bytes).decode('ascii'),
            'version': embedding_obj.embedding_version,
        }
    except Exception:
        # No face data registered yet — that is fine
        pass

    return payload


# ── Core sync function ─────────────────────────────────────────────────────

def sync_record(beneficiary, api_url: str, api_key: str, timeout: int = 30) -> bool:
    """
    Send a single Beneficiary record to the central API.

    Returns True on success, False on failure.
    Updates beneficiary.is_synced, beneficiary.last_synced_at,
    and beneficiary.sync_error in-place and saves.
    """
    import requests

    endpoint = api_url.rstrip('/') + '/beneficiaries/sync/'
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
        'X-FANS-Device': _device_id(),
    }

    try:
        payload = _build_payload(beneficiary)
        response = requests.post(endpoint, json=payload, headers=headers, timeout=timeout)
        response.raise_for_status()

        beneficiary.is_synced = True
        beneficiary.last_synced_at = datetime.now(dt_timezone.utc)
        beneficiary.sync_error = ''
        beneficiary.save(update_fields=['is_synced', 'last_synced_at', 'sync_error'])

        logger.info(
            'SYNC OK | beneficiary=%s id=%s',
            beneficiary.beneficiary_id,
            beneficiary.id,
        )
        return True

    except Exception as exc:
        error_msg = str(exc)
        beneficiary.sync_error = error_msg[:500]
        beneficiary.save(update_fields=['sync_error'])

        logger.warning(
            'SYNC FAIL | beneficiary=%s id=%s error=%s',
            beneficiary.beneficiary_id,
            beneficiary.id,
            error_msg,
        )
        return False


def sync_all(batch_size: int = 50) -> dict:
    """
    Sync all unsynced Beneficiary records to the central server.

    Returns a summary dict:
        {
            'synced':  int,   # successfully synced this run
            'failed':  int,   # failed (will be retried next run)
            'skipped': int,   # skipped because SYNC_API_URL is not configured
        }
    """
    from django.conf import settings
    from beneficiaries.models import Beneficiary

    api_url = getattr(settings, 'SYNC_API_URL', '').strip()
    api_key = getattr(settings, 'SYNC_API_KEY', '').strip()
    timeout = int(getattr(settings, 'SYNC_TIMEOUT', 30))

    if not api_url:
        logger.debug('SYNC SKIP | SYNC_API_URL is not configured — offline mode only')
        return {'synced': 0, 'failed': 0, 'skipped': 1}

    pending = Beneficiary.objects.filter(is_synced=False).order_by('created_at')[:batch_size]
    count = pending.count()

    if count == 0:
        logger.debug('SYNC OK | No unsynced records found')
        return {'synced': 0, 'failed': 0, 'skipped': 0}

    logger.info('SYNC START | %d record(s) to sync', count)
    synced = 0
    failed = 0

    for beneficiary in pending:
        if sync_record(beneficiary, api_url, api_key, timeout):
            synced += 1
        else:
            failed += 1

    logger.info('SYNC DONE | synced=%d failed=%d', synced, failed)
    return {'synced': synced, 'failed': failed, 'skipped': 0}


# ── Helpers ────────────────────────────────────────────────────────────────

def _device_id() -> str:
    """
    Return a stable device identifier (hostname) for the X-FANS-Device header.
    The central server can use this to identify which barangay workstation
    sent a record.
    """
    try:
        return socket.gethostname()
    except Exception:
        return 'unknown'


def pending_count() -> int:
    """Return the number of beneficiary records not yet synced."""
    from beneficiaries.models import Beneficiary
    return Beneficiary.objects.filter(is_synced=False).count()
