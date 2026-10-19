# MusicZone

## Run locally

Install dependencies, apply Django's built-in auth migrations, then start the server:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
py manage.py migrate
py manage.py runserver
```

The project stores profile uploads under `user_uploads/profile_pics/` and serves them at `/media/` during local development. Profile photo uploads require Pillow, which is included in `requirements.txt`.

Product CRUD is available to signed-in users at `/products/`. Add or edit products through the ModelForm pages; deletion requires a confirmation page and a CSRF-protected POST.

AJAX examples are available at `/ajax-demos/` for playlist songs and Watch Later movies. Product removal on `/products/` also uses fetch with a JSON DELETE request; successful responses remove the matching row from the DOM and announce the result without a reload.

## ORM QuerySet examples

Run `py manage.py migrate` after pulling model changes. Add categories, products, restaurants, movies, and reviews through `/admin/` (create a superuser with `py manage.py createsuperuser`). The product page is paginated five items at a time, loads categories with `select_related()`, and demonstrates `Q(category__name='Electronics') | Q(price__lt=1000)` plus optional search/category/price filters. The restaurant filter and annotated movie review count are at `/restaurants/` and `/movies/review-counts/`.

The requested email exclusion can be run in the Django shell:

```python
from django.contrib.auth.models import User
users_without_gmail = User.objects.exclude(email__contains="gmail.com")
```

The movie count page uses `Movie.objects.prefetch_related("reviews").annotate(review_count=Count("reviews"))`; the product list uses `Product.objects.select_related("category")` to load each category in the same query.

## Roles and permissions

After migrating, run `py manage.py setup_roles` to create the `Seller`, `Buyer`, `MovieCritic`, `MovieFan`, and `Admin` groups with their permissions. New signups join `Buyer`; promote a user to `Seller` in Django admin to grant product management access. Login redirects to `/dashboard/`, which routes Seller and Buyer users to their own dashboards. `/my-orders/` only shows the signed-in user's orders. The `Playlist` admin page is restricted to the `Admin` group; a user must also be marked staff to enter Django admin at all.

## External integrations

Set Google OAuth client ID and secret in `.env` to enable **Login with Google**. Register `http://localhost:8000/oauth/complete/google-oauth2/` as an authorized redirect URI in Google Cloud Console. Signup uses Mailgun's HTTP API when `MAILGUN_API_KEY` and `MAILGUN_DOMAIN` are set; otherwise it uses the configured Django email backend. SMS verification requires Twilio account SID, auth token, and sender number. Add a 10-digit number to your profile, then use **Send SMS verification code**. OTPs are stored as password hashes, expire after five minutes, and allow at most five attempts. Apply migrations after installing the added integration packages.

## Gmail SMTP

The project loads Gmail SMTP credentials from a local `.env` file, which is ignored by Git. Update those values as needed. `EMAIL_HOST_PASSWORD` must be a Google App Password; a normal Gmail account password will not work. Do not commit real credentials.

To send a simple SMTP configuration test to an address you control:

```powershell
py manage.py shell -c "from django.core.mail import send_mail; from django.conf import settings; send_mail('MusicZone SMTP test', 'Your Django email setup is working.', settings.DEFAULT_FROM_EMAIL, ['you@example.com'])"
```

Replace `you@example.com` with your own test address. Signup sends a welcome email. The home page also provides sample password-reset, order-confirmation, and IPL Fantasy League email forms. The order and IPL samples send to the signed-in account email; the password reset link uses Django's signed, time-limited built-in reset flow.

## Payment gateway sandbox demo

The separate Flask demo in `payments_flask/` provides IPL ticket checkout through Paytm staging and PayPal sandbox, plus a Stripe test-mode food-order Checkout flow. Install `requirements.txt`, copy `.env.example` to `.env`, set a strong `FLASK_SECRET_KEY`, and fill in the provider sandbox credentials. Then run:

```powershell
py payments_flask/app.py
```

Open `http://127.0.0.1:5001/`. Paytm ticket form: `/pay`; Stripe food order form: `/food-order`; PayPal ticket form: `/paypal/pay`. For Paytm callbacks and provider return URLs, expose the app through a public HTTPS tunnel and set `PAYMENTS_PUBLIC_BASE_URL` to its origin, for example `https://example-tunnel.test`. Configure that same public base with Paytm as the callback URL (`/payment-callback`). Use Stripe `sk_test_...` credentials and PayPal sandbox app credentials; never place live keys in the repo. The demo records order state locally in `payments_flask/payments.sqlite3` and verifies provider status server-side before showing success.

Paytm uses staging transaction initiate and status APIs with checksum validation; Stripe uses hosted Checkout Sessions; PayPal creates sandbox Orders and captures after approval. See the [Paytm server SDK and checksum docs](https://business.paytm.com/docs/server-sdk/), [Stripe Checkout API](https://docs.stripe.com/api/checkout/sessions/create), and [PayPal Checkout integration guide](https://developer.paypal.com/checkout/integrate).

## Maps and geolocation

Set `GOOGLE_MAPS_API_KEY` in `.env` after enabling the Google Maps Geocoding API and Maps Embed API in Google Cloud Console. Run `py geocode_address.py "IIM Ahmedabad, Gujarat"` to print coordinates. The restaurant map demo is at `/restaurant-location/`; pickup-point search is at `/pickup-points/`. The latter geocodes five sample pickup addresses and sorts results by Haversine distance. Google Maps API usage may require billing and API key restrictions; configure those in Google Cloud.
