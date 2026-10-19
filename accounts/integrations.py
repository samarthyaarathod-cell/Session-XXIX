import requests
from django.conf import settings
from django.core.mail import send_mail


def send_welcome_email(user):
    """Send the signup welcome message using Mailgun when configured, else Django SMTP."""
    subject = "Welcome to MusicZone!"
    body = f"Hi {user.username},\n\nWelcome to MusicZone! Your account is ready. Start exploring.\n\nThe MusicZone team"
    if settings.MAILGUN_API_KEY and settings.MAILGUN_DOMAIN:
        response = requests.post(
            f"{settings.MAILGUN_API_BASE_URL.rstrip('/')}/{settings.MAILGUN_DOMAIN}/messages",
            auth=("api", settings.MAILGUN_API_KEY),
            data={
                "from": f"MusicZone <{settings.DEFAULT_FROM_EMAIL}>",
                "to": [user.email],
                "subject": subject,
                "text": body,
            },
            timeout=15,
        )
        response.raise_for_status()
        return
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)


def send_twilio_sms(phone_number, body):
    """Submit one SMS using Twilio's Messages REST endpoint."""
    required = (settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN, settings.TWILIO_PHONE_NUMBER)
    if not all(required):
        raise RuntimeError("Twilio credentials are not configured.")
    normalized_number = phone_number.strip()
    if normalized_number.startswith("00"):
        normalized_number = f"+{normalized_number[2:]}"
    elif not normalized_number.startswith("+"):
        normalized_number = f"{settings.TWILIO_DEFAULT_COUNTRY_CODE}{normalized_number}"
    response = requests.post(
        f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json",
        auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
        data={"From": settings.TWILIO_PHONE_NUMBER, "To": normalized_number, "Body": body},
        timeout=15,
    )
    response.raise_for_status()
