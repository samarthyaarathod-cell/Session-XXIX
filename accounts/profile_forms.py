from django import forms

from .models import InfluencerProfile


class InfluencerProfileForm(forms.ModelForm):
    phone_number = forms.RegexField(
        regex=r"^\d{10}$",
        max_length=10,
        error_messages={"invalid": "Enter a phone number with exactly 10 digits."},
    )

    class Meta:
        model = InfluencerProfile
        fields = ("display_name", "bio", "phone_number", "profile_pic")
        widgets = {"bio": forms.Textarea(attrs={"rows": 4})}
