from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models


class InfluencerProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="influencer_profile")
    display_name = models.CharField(max_length=100, blank=True)
    bio = models.TextField(blank=True)
    profile_pic = models.ImageField(upload_to="profile_pics/", blank=True)
    phone_number = models.CharField(
        max_length=10,
        blank=True,
        validators=[RegexValidator(r"^\d{10}$", "Enter a phone number with exactly 10 digits.")],
    )
    phone_verified = models.BooleanField(default=False)

    def __str__(self):
        return self.display_name or self.user.username


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")

    def __str__(self):
        return self.name


class Restaurant(models.Model):
    name = models.CharField(max_length=200)
    cuisine = models.CharField(max_length=100)
    rating = models.DecimalField(max_digits=2, decimal_places=1)

    def __str__(self):
        return self.name


class Movie(models.Model):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name


class Review(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name="reviews")
    reviewer_name = models.CharField(max_length=100)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Review for {self.movie.name} by {self.reviewer_name}"


class Playlist(models.Model):
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return self.name


class Order(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orders")
    order_number = models.CharField(max_length=30, unique=True)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=30, default="Processing")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return self.order_number


class SmsOTP(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sms_otps")
    phone_number = models.CharField(max_length=20)
    code_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    consumed = models.BooleanField(default=False)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"SMS OTP for {self.user.username}"
