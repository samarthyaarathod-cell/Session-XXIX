import django.core.validators
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="InfluencerProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("display_name", models.CharField(blank=True, max_length=100)),
                ("bio", models.TextField(blank=True)),
                ("profile_pic", models.ImageField(blank=True, upload_to="profile_pics/")),
                ("phone_number", models.CharField(blank=True, max_length=10, validators=[django.core.validators.RegexValidator(r"^\d{10}$", "Enter a phone number with exactly 10 digits.")])),
                ("user", models.OneToOneField(on_delete=models.deletion.CASCADE, related_name="influencer_profile", to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
