import logging

from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from core.middleware import camping_hosts, forget_hosts

from .models import BookingPolicy, Camping, Photo

logger = logging.getLogger(__name__)


def _delete_name(storage, name):
    """Remove a stored file once the surrounding transaction commits."""

    def delete():
        try:
            storage.delete(name)
        except Exception:  # noqa: BLE001 - a missing file must not break deletes
            logger.warning("Could not delete stored file %s", name, exc_info=True)

    transaction.on_commit(delete)


def _delete_file(field_file):
    if field_file:
        _delete_name(field_file.storage, field_file.name)


@receiver(post_save, sender=Camping)
def create_default_policy(sender, instance, created, **kwargs):
    if created:
        BookingPolicy.objects.get_or_create(camping=instance)


@receiver(pre_save, sender=Camping)
def remember_previous_values(sender, instance, **kwargs):
    if not instance.pk:
        instance._previous = {}
        return
    previous = (
        Camping.objects.filter(pk=instance.pk).values("custom_domain", "domain_verified_at", "slug", "logo").first()
        or {}
    )
    instance._previous = previous
    if previous.get("custom_domain") != instance.custom_domain:
        # A new domain has to prove again that its DNS points here.
        instance.domain_verified_at = None
    elif instance.domain_verified_at is None:
        # Do not lose a verification that happened while the form was open.
        instance.domain_verified_at = previous.get("domain_verified_at")


@receiver(post_save, sender=Camping)
def cleanup_after_camping_change(sender, instance, created, **kwargs):
    previous = getattr(instance, "_previous", {}) or {}
    forget_hosts(
        *camping_hosts(slug=previous.get("slug"), custom_domain=previous.get("custom_domain")),
        *camping_hosts(slug=instance.slug, custom_domain=instance.custom_domain),
    )
    old_logo = previous.get("logo")
    if old_logo and old_logo != instance.logo.name:
        _delete_name(instance.logo.storage, old_logo)


@receiver(post_delete, sender=Camping)
def delete_camping_files(sender, instance, **kwargs):
    forget_hosts(*camping_hosts(slug=instance.slug, custom_domain=instance.custom_domain))
    _delete_file(instance.logo)


@receiver(post_delete, sender=Photo)
def delete_photo_files(sender, instance, **kwargs):
    _delete_file(instance.image)
    _delete_file(instance.thumbnail)
