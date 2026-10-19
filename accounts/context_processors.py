from django.conf import settings


def integration_flags(request):
    return {
        "google_oauth_enabled": bool(
            settings.SOCIAL_AUTH_GOOGLE_OAUTH2_KEY and settings.SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET
        )
    }
