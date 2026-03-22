from django import template
from django.utils.html import mark_safe, escape

register = template.Library()

# Human-readable labels for common audit log detail keys
_KEY_LABELS = {
    'beneficiary_id':   'Beneficiary ID',
    'beneficiary':      'Beneficiary',
    'decision':         'Decision',
    'score':            'Score',
    'similarity_score': 'Similarity Score',
    'threshold':        'Threshold',
    'reason':           'Reason',
    'action':           'Action',
    'action_label':     'Action Label',
    'notes':            'Notes',
    'id_type':          'ID Type',
    'id_verified':      'ID Verified',
    'claimant_type':    'Claimant Type',
    'liveness_passed':  'Liveness Passed',
    'liveness_score':   'Liveness Score',
    'event':            'Event',
    'quality_ok':       'Quality OK',
    'key':              'Config Key',
    'old_value':        'Old Value',
    'new_value':        'New Value',
    'attempt_id':       'Attempt ID',
    'review_notes':     'Review Notes',
    'template':         'Template',
    'templates_checked': 'Templates Checked',
    'original_score':   'Original Score',
    'stipend_event':    'Stipend Event',
    'via':              'Via',
}


@register.filter
def format_audit_details(details):
    """
    Renders a dict of audit log details as a small labeled key-value list.
    Returns an empty string for falsy input.
    """
    if not details or not isinstance(details, dict):
        return ''

    parts = []
    for k, v in details.items():
        label = _KEY_LABELS.get(k, k.replace('_', ' ').title())
        if v is None:
            display = mark_safe('&mdash;')
        elif isinstance(v, bool):
            display = 'Yes' if v else 'No'
        elif isinstance(v, float):
            display = f'{v:.4f}'
        else:
            display = escape(str(v))
        parts.append(
            mark_safe(
                f'<span class="text-muted">{escape(label)}:</span> '
                f'<strong>{display}</strong>'
            )
        )

    return mark_safe(mark_safe(' &bull; ').join(parts))
