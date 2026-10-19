from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "password1", "password2")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class ForgotPasswordForm(forms.Form):
    email = forms.EmailField(label="Account email")


class VerifyOTPForm(forms.Form):
    otp = forms.CharField(label="6-digit code", min_length=6, max_length=6)
    new_password1 = forms.CharField(label="New password", widget=forms.PasswordInput)
    new_password2 = forms.CharField(label="Confirm new password", widget=forms.PasswordInput)

    def clean_otp(self):
        otp = self.cleaned_data["otp"]
        if not otp.isdecimal():
            raise forms.ValidationError("Enter the 6-digit code from your email.")
        return otp

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("new_password1") and cleaned_data.get("new_password2") and cleaned_data["new_password1"] != cleaned_data["new_password2"]:
            self.add_error("new_password2", "The passwords do not match.")
        return cleaned_data


class VerifySMSOTPForm(forms.Form):
    otp = forms.RegexField(
        regex=r"^\d{6}$",
        max_length=6,
        error_messages={"invalid": "Enter the 6-digit code from your text message."},
    )
