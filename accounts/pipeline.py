import logging

from django.contrib.auth.models import Group

from .integrations import send_welcome_email

logger = logging.getLogger(__name__)


def configure_new_social_user(backend, user, is_new=False, **kwargs):
    """Give new Google users the default Buyer role and send the signup email."""
    if is_new:
        buyer_group = Group.objects.filter(name="Buyer").first()
        if buyer_group:
            user.groups.add(buyer_group)
        try:
            send_welcome_email(user)
        except Exception:
            logger.exception("Could not send the social signup welcome email for user %s", user.pk)
    return {"user": user}
