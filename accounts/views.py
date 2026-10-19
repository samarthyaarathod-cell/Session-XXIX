from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone
from django.core.mail import EmailMultiAlternatives, send_mail
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponseBadRequest, JsonResponse
from django.contrib.auth.models import Group, User
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_GET, require_POST, require_http_methods
import json
import secrets
import time
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from requests.exceptions import RequestException
import math

from .forms import ForgotPasswordForm, SignUpForm, VerifyOTPForm, VerifySMSOTPForm
from .integrations import send_twilio_sms, send_welcome_email
from .models import InfluencerProfile, Movie, Order, Product, Restaurant, SmsOTP
from .profile_forms import InfluencerProfileForm
from .product_forms import ProductForm


def home(request):
    return render(request, "home.html")


def signup(request):
    if request.user.is_authenticated:
        return redirect("welcome")
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            buyer_group = Group.objects.filter(name="Buyer").first()
            if buyer_group:
                user.groups.add(buyer_group)
            try:
                send_welcome_email(user)
            except Exception:
                # A mail outage should not prevent account creation.
                pass
            login(request, user)
            return redirect("dashboard_router")
    else:
        form = SignUpForm()
    return render(request, "registration/signup.html", {"form": form})


@require_GET
def welcome(request):
    if not request.user.is_authenticated:
        return redirect("login")
    return render(request, "welcome.html")


def _has_role_permission(user, group_name, permission_codename):
    return user.is_authenticated and user.groups.filter(name=group_name).exists() and user.has_perm(
        f"accounts.{permission_codename}"
    )


@login_required
def dashboard_router(request):
    if request.user.groups.filter(name="Seller").exists():
        return redirect("seller_dashboard")
    if request.user.groups.filter(name="Buyer").exists():
        return redirect("buyer_dashboard")
    return redirect("welcome")


@login_required
def seller_dashboard(request):
    if not request.user.groups.filter(name="Seller").exists():
        raise PermissionDenied
    return render(request, "dashboards/seller.html", {"product_count": Product.objects.count()})


@login_required
def buyer_dashboard(request):
    if not request.user.groups.filter(name="Buyer").exists():
        raise PermissionDenied
    orders = Order.objects.filter(user=request.user)
    return render(request, "dashboards/buyer.html", {"orders": orders, "order_count": orders.count()})


@login_required
def my_orders_view(request):
    orders = Order.objects.filter(user=request.user)
    return render(request, "orders/my_orders.html", {"orders": orders})


@login_required
def profile_view(request):
    profile, _ = InfluencerProfile.objects.get_or_create(user=request.user)
    return render(request, "accounts/profile.html", {"profile": profile})


@login_required
def profile_edit_view(request):
    profile, _ = InfluencerProfile.objects.get_or_create(user=request.user)
    if request.method == "POST":
        form = InfluencerProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            if form.cleaned_data["phone_number"] != profile.phone_number:
                profile.phone_verified = False
            form.save()
            messages.success(request, "Your profile was updated.")
            return redirect("profile")
    else:
        form = InfluencerProfileForm(instance=profile)
    return render(request, "accounts/profile_edit.html", {"form": form, "profile": profile})


@login_required
@require_POST
def send_sms_otp_view(request):
    profile, _ = InfluencerProfile.objects.get_or_create(user=request.user)
    if not profile.phone_number:
        messages.error(request, "Add a valid 10-digit phone number to your profile first.")
        return redirect("profile_edit")
    code = f"{secrets.randbelow(1_000_000):06d}"
    try:
        send_twilio_sms(
            profile.phone_number,
            f"Your MusicZone verification code is {code}. It expires in 5 minutes.",
        )
    except (RequestException, RuntimeError):
        messages.error(request, "We couldn't send an SMS right now. Check the Twilio setup and try again.")
        return redirect("profile")

    SmsOTP.objects.filter(user=request.user, consumed=False).update(consumed=True)
    SmsOTP.objects.create(
        user=request.user,
        phone_number=profile.phone_number,
        code_hash=make_password(code),
        expires_at=timezone.now() + timedelta(minutes=5),
    )
    messages.success(request, "OTP sent to your registered mobile number.")
    return redirect("verify_sms_otp")


@login_required
def verify_sms_otp_view(request):
    otp_record = SmsOTP.objects.filter(user=request.user, consumed=False).first()
    if otp_record is None:
        messages.info(request, "Request a new SMS code to continue.")
        return redirect("profile")
    if timezone.now() >= otp_record.expires_at or otp_record.attempts >= 5:
        otp_record.consumed = True
        otp_record.save(update_fields=["consumed"])
        messages.error(request, "That code has expired or reached its attempt limit. Request a new code.")
        return redirect("profile")

    form = VerifySMSOTPForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        otp_record.attempts += 1
        if check_password(form.cleaned_data["otp"], otp_record.code_hash):
            otp_record.consumed = True
            otp_record.save(update_fields=["attempts", "consumed"])
            profile, _ = InfluencerProfile.objects.get_or_create(user=request.user)
            if profile.phone_number == otp_record.phone_number:
                profile.phone_verified = True
                profile.save(update_fields=["phone_verified"])
            messages.success(request, "Phone number verified successfully.")
            return redirect("profile")
        if otp_record.attempts >= 5:
            otp_record.consumed = True
            form.add_error("otp", "Too many incorrect attempts. Request a new code.")
        else:
            form.add_error("otp", "That code is incorrect. Try again.")
        otp_record.save(update_fields=["attempts", "consumed"])
    return render(request, "accounts/verify_sms_otp.html", {"form": form, "expires_at": otp_record.expires_at})


@login_required
def product_list_view(request):
    search_query = request.GET.get("q", "").strip()
    selected_category = request.GET.get("category", "").strip()
    max_price = request.GET.get("max_price", "").strip()

    # Required example: Electronics products OR products under ₹1,000.
    products = Product.objects.select_related("category").filter(
        Q(category__name__iexact="Electronics") | Q(price__lt=1000)
    )
    if search_query:
        products = products.filter(Q(name__icontains=search_query) | Q(category__name__icontains=search_query))
    if selected_category:
        products = products.filter(category__name__iexact=selected_category)
    if max_price:
        try:
            max_price_value = Decimal(max_price)
            if max_price_value < 0:
                raise InvalidOperation
            products = products.filter(price__lte=max_price_value)
        except (InvalidOperation, ValueError, TypeError):
            max_price = ""
    products = products.order_by("name")
    page_obj = Paginator(products, 5).get_page(request.GET.get("page"))
    categories = Product.objects.order_by("category__name").values_list("category__name", flat=True).distinct()
    return render(request, "products/product_list.html", {
        "products": page_obj.object_list,
        "page_obj": page_obj,
        "categories": categories,
        "search_query": search_query,
        "selected_category": selected_category,
        "max_price": max_price,
        "is_seller": request.user.groups.filter(name="Seller").exists(),
    })


@require_GET
def restaurant_search_view(request):
    restaurants = Restaurant.objects.filter(cuisine__iexact="Chinese", rating__gt=4).order_by("name")
    return render(request, "query_demos/restaurants.html", {"restaurants": restaurants})


@require_GET
def movie_review_counts_view(request):
    movies = Movie.objects.prefetch_related("reviews").annotate(review_count=Count("reviews")).order_by("name")
    return render(request, "query_demos/movie_review_counts.html", {"movies": movies})


def geocode_address(address):
    """Resolve an address with Google's Geocoding API; return (lat, lng) or None."""
    api_key = getattr(settings, "GOOGLE_MAPS_API_KEY", "")
    if not api_key:
        return None
    try:
        response = requests.get(
            "https://maps.googleapis.com/maps/api/geocode/json",
            params={"address": address, "key": api_key}, timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
    except (RequestException, ValueError):
        return None
    if payload.get("status") != "OK" or not payload.get("results"):
        return None
    location = payload["results"][0]["geometry"]["location"]
    return float(location["lat"]), float(location["lng"])


def find_nearby_cafes(user_lat, user_lng, cafes):
    """Return cafe dictionaries within 3 km, with a computed distance_km field."""
    earth_radius_km = 6371.0
    nearby = []
    for cafe in cafes:
        lat1, lat2 = math.radians(float(user_lat)), math.radians(float(cafe["lat"]))
        delta_lat = lat2 - lat1
        delta_lng = math.radians(float(cafe["lng"]) - float(user_lng))
        haversine = (math.sin(delta_lat / 2) ** 2
                     + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lng / 2) ** 2)
        distance = 2 * earth_radius_km * math.asin(min(1.0, math.sqrt(haversine)))
        if distance <= 3:
            nearby.append({**cafe, "distance_km": distance})
    return nearby


@require_http_methods(["GET", "POST"])
def show_restaurant_location(request):
    address = request.POST.get("address", "").strip() if request.method == "POST" else request.GET.get("address", "").strip()
    location = geocode_address(address) if address else None
    if address and location is None:
        messages.error(request, "We couldn't find that address. Check it and try again.")
    return render(request, "maps/restaurant_location.html", {
        "address": address, "location": location,
        "maps_api_key": getattr(settings, "GOOGLE_MAPS_API_KEY", ""),
    })


PICKUP_POINTS = [
    {"name": "Ahmedabad Central Pickup", "address": "IIM Ahmedabad, Vastrapur, Ahmedabad, Gujarat"},
    {"name": "Gandhinagar Pickup", "address": "Sector 21, Gandhinagar, Gujarat"},
    {"name": "Vadodara Pickup", "address": "Alkapuri, Vadodara, Gujarat"},
    {"name": "Surat Pickup", "address": "Adajan, Surat, Gujarat"},
    {"name": "Rajkot Pickup", "address": "Kalawad Road, Rajkot, Gujarat"},
]


@require_http_methods(["GET", "POST"])
def search_by_distance(request):
    address = request.POST.get("address", "").strip() if request.method == "POST" else request.GET.get("address", "").strip()
    origin = geocode_address(address) if address else None
    points = []
    error = ""
    if address and origin is None:
        error = "Address couldn't be geocoded. Check the address and try again."
    elif origin:
        for pickup in PICKUP_POINTS:
            coordinates = geocode_address(pickup["address"])
            if coordinates:
                points.append({**pickup, "lat": coordinates[0], "lng": coordinates[1]})
        points = find_nearby_cafes(origin[0], origin[1], points)
        points.sort(key=lambda point: point["distance_km"])
        if not points:
            error = "Pickup point locations are unavailable. Check the Google Maps API key and Geocoding API settings."
    return render(request, "maps/pickup_search.html", {
        "address": address, "pickup_points": points, "error": error,
        "origin": origin,
    })


@login_required
def product_create_view(request):
    if not _has_role_permission(request.user, "Seller", "add_product"):
        raise PermissionDenied
    form = ProductForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Product added.")
        return redirect("product_list")
    return render(request, "products/product_form.html", {"form": form, "title": "Add product"})


@login_required
def product_edit_view(request, pk):
    if not _has_role_permission(request.user, "Seller", "change_product"):
        raise PermissionDenied
    product = get_object_or_404(Product, pk=pk)
    form = ProductForm(request.POST or None, instance=product)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Product updated.")
        return redirect("product_list")
    return render(request, "products/product_form.html", {"form": form, "title": "Edit product", "product": product})


@login_required
def product_delete_view(request, pk):
    if not _has_role_permission(request.user, "Seller", "delete_product"):
        raise PermissionDenied
    product = get_object_or_404(Product, pk=pk)
    if request.method == "POST":
        product.delete()
        messages.success(request, "Product deleted.")
        return redirect("product_list")
    return render(request, "products/product_confirm_delete.html", {"product": product})


@require_http_methods(["DELETE"])
def product_delete_ajax_view(request, pk):
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False, "message": "Please log in to manage products."}, status=401)
    if not _has_role_permission(request.user, "Seller", "delete_product"):
        return JsonResponse({"ok": False, "message": "Only sellers with product delete permission can remove products."}, status=403)
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "message": "Invalid JSON request."}, status=400)
    if not isinstance(payload, dict) or payload.get("product_id") != pk:
        return JsonResponse({"ok": False, "message": "Product id did not match the request."}, status=400)
    product = get_object_or_404(Product, pk=pk)
    product_name = product.name
    product.delete()
    return JsonResponse({"ok": True, "message": f"{product_name} was removed.", "product_id": pk})


@require_GET
def ajax_demos_view(request):
    request.session.setdefault("demo_songs", [
        {"id": "song-1", "name": "Midnight City"},
        {"id": "song-2", "name": "Golden Hour"},
        {"id": "song-3", "name": "Electric Feel"},
    ])
    request.session.setdefault("watch_later", [
        {"id": "movie-1", "name": "The Grand Journey"},
        {"id": "movie-2", "name": "Beyond the Stars"},
    ])
    return render(request, "ajax_demos.html", {
        "songs": request.session["demo_songs"],
        "movies": request.session["watch_later"],
    })


@require_http_methods(["DELETE"])
def delete_demo_item_view(request, kind, item_id):
    collections = {"songs": "demo_songs", "watch-later": "watch_later"}
    session_key = collections.get(kind)
    if not session_key:
        return JsonResponse({"ok": False, "message": "Unknown list."}, status=404)
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "message": "Invalid JSON request."}, status=400)
    if not isinstance(payload, dict) or payload.get("id") != item_id:
        return JsonResponse({"ok": False, "message": "Item id did not match the request."}, status=400)
    items = request.session.get(session_key, [])
    item = next((entry for entry in items if entry["id"] == item_id), None)
    if item is None:
        return JsonResponse({"ok": False, "message": "That item is no longer in the list."}, status=404)
    request.session[session_key] = [entry for entry in items if entry["id"] != item_id]
    label = "song" if kind == "songs" else "movie"
    return JsonResponse({"ok": True, "message": f'{item["name"]} was removed from {"your playlist" if kind == "songs" else "Watch Later"}.', "id": item_id, "type": label})


def forgot_password_view(request):
    if request.method == "POST":
        form = ForgotPasswordForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            user = User.objects.filter(email__iexact=email, is_active=True).first()
            # Clear any older reset challenge before starting another one.
            for key in ("otp", "otp_email", "otp_expires_at", "otp_attempts"):
                request.session.pop(key, None)
            if user:
                otp = f"{secrets.randbelow(1_000_000):06d}"
                try:
                    send_mail(
                        "Your MusicZone password reset code",
                        f"Hi {user.username},\n\nYour password reset code is {otp}. It expires in 5 minutes. If you didn't request this, ignore this message.",
                        settings.DEFAULT_FROM_EMAIL,
                        [user.email],
                        fail_silently=False,
                    )
                except Exception:
                    form.add_error(None, "We couldn't send the email right now. Please try again shortly.")
                else:
                    request.session["otp"] = otp
                    request.session["otp_email"] = user.email
                    request.session["otp_expires_at"] = int(time.time()) + 300
                    request.session["otp_attempts"] = 0
                    request.session.set_expiry(300)
                    return redirect("verify_otp")
            else:
                # Keep response behavior the same to avoid exposing registered accounts.
                messages.info(request, "If an active account uses that email, a reset code has been sent.")
                return redirect("login")
    else:
        form = ForgotPasswordForm()
    return render(request, "registration/forgot_password.html", {"form": form})


def verify_otp_view(request):
    if request.method == "POST":
        form = VerifyOTPForm(request.POST)
        if form.is_valid():
            expected = request.session.get("otp")
            if expected is None:
                return redirect("forgot_password")
            if not secrets.compare_digest(form.cleaned_data["otp"], expected):
                attempts = request.session.get("otp_attempts", 0) + 1
                request.session["otp_attempts"] = attempts
                if attempts >= 5:
                    for key in ("otp", "otp_email", "otp_expires_at", "otp_attempts"):
                        request.session.pop(key, None)
                    form.add_error("otp", "Too many incorrect attempts. Request a new reset code.")
                else:
                    form.add_error("otp", "That code is incorrect. Please try again.")
            else:
                user = User.objects.filter(email__iexact=request.session.get("otp_email", ""), is_active=True).first()
                if user is None:
                    request.session.flush()
                    return redirect("forgot_password")
                password = form.cleaned_data["new_password1"]
                try:
                    validate_password(password, user=user)
                except ValidationError as exc:
                    for error in exc.error_list:
                        form.add_error("new_password1", error)
                else:
                    user.set_password(password)
                    user.save(update_fields=["password"])
                    request.session.flush()
                    messages.success(request, "Your password has been reset. You can now log in.")
                    return redirect("login")
    else:
        form = VerifyOTPForm()
    return render(request, "registration/verify_otp.html", {"form": form})


@require_POST
def send_password_reset_email(request, user_email=None):
    """Send Django's signed, time-limited password reset link by email."""
    email = user_email or request.POST.get("email", "")
    form = PasswordResetForm({"email": email})
    if not form.is_valid():
        return HttpResponseBadRequest("Enter a valid email address.")
    form.save(
        request=request,
        use_https=request.is_secure(),
        email_template_name="registration/password_reset_email.txt",
        subject_template_name="registration/password_reset_subject.txt",
        from_email=settings.DEFAULT_FROM_EMAIL,
        extra_email_context={"site_name": "MusicZone"},
    )
    return render(request, "email_sent.html", {"message": "If an account uses that email, a password reset link is on its way."})


@require_POST
def send_order_confirmation(request):
    """Demonstration endpoint for sending an HTML order receipt to a signed-in user."""
    if not request.user.is_authenticated:
        return redirect("login")
    order = {
        "number": request.POST.get("order_number", "MZ-1042"),
        "items": request.POST.get("items", "Acoustic Playlist, Studio Headphones").split(","),
        "total": request.POST.get("total", "₹1,499"),
    }
    context = {"name": request.user.get_full_name() or request.user.username, "order": order}
    html = render_to_string("emails/order_confirmation.html", context)
    text = render_to_string("emails/order_confirmation.txt", context)
    message = EmailMultiAlternatives(
        subject=f"Order {order['number']} confirmed — your MusicZone picks are on their way",
        body=text,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[request.user.email],
    )
    message.attach_alternative(html, "text/html")
    message.send(fail_silently=False)
    return render(request, "email_sent.html", {"message": "Your order confirmation email has been sent."})


@require_POST
def send_ipl_welcome_email(request):
    """Send the sample IPL Fantasy League welcome message to the signed-in user."""
    if not request.user.is_authenticated:
        return redirect("login")
    recipient = request.POST.get("email") or request.user.email
    if not recipient:
        return HttpResponseBadRequest("Add an email address to your account or provide one for this sample.")
    context = {"name": request.user.get_full_name() or request.user.username}
    html = render_to_string("emails/ipl_welcome.html", context)
    text = render_to_string("emails/ipl_welcome.txt", context)
    message = EmailMultiAlternatives(
        subject="Your IPL season starts here — welcome to Fantasy League!",
        body=text,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient],
    )
    message.attach_alternative(html, "text/html")
    message.send(fail_silently=False)
    return render(request, "email_sent.html", {"message": f"IPL Fantasy League welcome email sent to {recipient}."})
