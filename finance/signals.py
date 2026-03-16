from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Transaction, AuditLog
from .services import evaluate_and_persist_risk_alert
from django_finances.middleware import get_current_request
import logging

logger = logging.getLogger(__name__)


def _get_request_ip():
    req = get_current_request()
    return req.META.get('REMOTE_ADDR') if req else None


@receiver(post_save, sender=Transaction)
def log_transaction_save(sender, instance, created, **kwargs):
    action = 'CREATE' if created else 'UPDATE'
    AuditLog.objects.create(
        user=instance.user,
        action=action,
        resource_type='Transaction',
        description=f"{action} transaction: {instance.amount_in_gbp} GBP ({instance.note or 'No note'})",
        ip_address=_get_request_ip(),
    )
    try:
        evaluate_and_persist_risk_alert(instance)
    except Exception:
        logger.exception("Risk evaluation failed for transaction_id=%s", instance.id)

@receiver(post_delete, sender=Transaction)
def log_transaction_delete(sender, instance, **kwargs):
    AuditLog.objects.create(
        user=instance.user,
        action='DELETE',
        resource_type='Transaction',
        description=f"Deleted transaction: {instance.amount_in_gbp} GBP",
        ip_address=_get_request_ip(),
    )
