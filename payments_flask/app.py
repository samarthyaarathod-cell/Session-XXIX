"""Standalone Flask sandbox demos for Paytm, Stripe Checkout, and PayPal."""
import hmac
import json
import os
import re
import secrets
import sqlite3
import uuid
from decimal import Decimal, InvalidOperation
from pathlib import Path

import requests
import stripe
from dotenv import load_dotenv
from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from paytmchecksum import PaytmChecksum

ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR.parent / ".env")

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "replace-this-local-demo-secret")
app.config["DATABASE"] = os.environ.get("PAYMENTS_DATABASE", str(ROOT_DIR / "payments.sqlite3"))

PAYTM_STAGE = os.environ.get("PAYTM_STAGING_BASE_URL", "https://securegw-stage.paytm.in").rstrip("/")
PAYPAL_API = "https://api-m.sandbox.paypal.com"


def db_connect():
    connection = sqlite3.connect(app.config["DATABASE"])
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with db_connect() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS payment_orders (
                id TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                item TEXT NOT NULL,
                amount TEXT NOT NULL,
                currency TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                provider_id TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)


def create_order(provider, name, email, item, amount, currency):
    order_id = uuid.uuid4().hex
    with db_connect() as connection:
        connection.execute(
            "INSERT INTO payment_orders (id, provider, name, email, item, amount, currency) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (order_id, provider, name, email, item, str(amount), currency),
        )
    return order_id


def get_order(order_id, provider=None):
    with db_connect() as connection:
        if provider:
            row = connection.execute(
                "SELECT * FROM payment_orders WHERE id = ? AND provider = ?", (order_id, provider)
            ).fetchone()
        else:
            row = connection.execute("SELECT * FROM payment_orders WHERE id = ?", (order_id,)).fetchone()
    return row


def update_order(order_id, *, status, provider_id=None):
    with db_connect() as connection:
        connection.execute(
            "UPDATE payment_orders SET status = ?, provider_id = COALESCE(?, provider_id) WHERE id = ?",
            (status, provider_id, order_id),
        )


def payment_url(endpoint, **values):
    path = url_for(endpoint, **values)
    public_base = os.environ.get("PAYMENTS_PUBLIC_BASE_URL", "").rstrip("/")
    return f"{public_base}{path}" if public_base else url_for(endpoint, _external=True, **values)


def parse_form_order(default_item):
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    item = request.form.get("item", default_item).strip() or default_item
    amount_text = request.form.get("amount", "").strip()
    if not name or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise ValueError("Enter your name and a valid email address.")
    try:
        amount = Decimal(amount_text).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        raise ValueError("Enter a valid payment amount.")
    if amount <= 0 or amount > Decimal("100000.00"):
        raise ValueError("Amount must be greater than 0 and no more than 100,000.")
    return name, email, item, amount


@app.before_request
def protect_forms_with_csrf():
    # The Paytm browser callback has its own signed checksum validation.
    if request.method != "POST" or request.endpoint == "payment_callback":
        return None
    token = session.get("_csrf_token")
    submitted = request.form.get("csrf_token", "")
    if not token or not hmac.compare_digest(token, submitted):
        abort(400, description="The form expired or its CSRF token was invalid. Please retry.")


@app.context_processor
def csrf_context():
    def csrf_token():
        token = session.get("_csrf_token")
        if not token:
            token = secrets.token_urlsafe(32)
            session["_csrf_token"] = token
        return token
    return {"csrf_token": csrf_token}


@app.get("/")
def index():
    return render_template("index.html")


@app.route("/pay", methods=["GET", "POST"])
def pay():
    if request.method == "GET":
        return render_template("paytm_form.html")
    try:
        name, email, _item, amount = parse_form_order("IPL match tickets")
    except ValueError as exc:
        flash(str(exc), "error")
        return render_template("paytm_form.html"), 400

    mid = os.environ.get("PAYTM_MID", "")
    merchant_key = os.environ.get("PAYTM_MERCHANT_KEY", "")
    if not mid or not merchant_key:
        flash("Paytm sandbox is not configured. Add PAYTM_MID and PAYTM_MERCHANT_KEY to .env.", "error")
        return render_template("paytm_form.html"), 503

    order_id = create_order("paytm", name, email, "IPL match tickets", amount, "INR")
    body = {
        "requestType": "Payment",
        "mid": mid,
        "websiteName": os.environ.get("PAYTM_WEBSITE", "WEBSTAGING"),
        "orderId": order_id,
        "txnAmount": {"value": f"{amount:.2f}", "currency": "INR"},
        "userInfo": {"custId": f"customer-{order_id[:16]}", "email": email},
        "callbackUrl": payment_url("payment_callback"),
    }
    signature = PaytmChecksum.generateSignature(json.dumps(body), merchant_key)
    try:
        response = requests.post(
            f"{PAYTM_STAGE}/theia/api/v1/initiateTransaction?mid={mid}&orderId={order_id}",
            json={"body": body, "head": {"signature": signature}},
            timeout=25,
        )
        response.raise_for_status()
        token = response.json().get("body", {}).get("txnToken")
        if not token:
            raise RuntimeError("Paytm did not return a transaction token.")
    except (requests.RequestException, ValueError, RuntimeError):
        update_order(order_id, status="failed")
        flash("Paytm could not start the sandbox payment. Check your staging credentials and try again.", "error")
        return render_template("paytm_form.html"), 502

    return render_template(
        "paytm_redirect.html",
        mid=mid,
        order_id=order_id,
        txn_token=token,
        action=f"{PAYTM_STAGE}/theia/api/v1/showPaymentPage?mid={mid}&orderId={order_id}",
    )


@app.post("/payment-callback")
def payment_callback():
    """Verify Paytm's callback checksum and confirm the result server-to-server."""
    merchant_key = os.environ.get("PAYTM_MERCHANT_KEY", "")
    mid = os.environ.get("PAYTM_MID", "")
    params = request.form.to_dict() or (request.get_json(silent=True) or {})
    checksum = params.pop("CHECKSUMHASH", None)
    order_id = params.get("ORDERID") or params.get("ORDER_ID")
    order = get_order(order_id or "", "paytm")
    if not merchant_key or not mid or not checksum or not order:
        return render_template("payment_result.html", order=order, success=False, message="Payment callback could not be verified."), 400
    try:
        callback_valid = PaytmChecksum.verifySignature(params, merchant_key, checksum)
        if not callback_valid:
            raise ValueError("Invalid callback signature")
        status_body = {"mid": mid, "orderId": order["id"]}
        status_signature = PaytmChecksum.generateSignature(json.dumps(status_body), merchant_key)
        response = requests.post(
            f"{PAYTM_STAGE}/v3/order/status",
            json={"body": status_body, "head": {"signature": status_signature}},
            timeout=25,
        )
        response.raise_for_status()
        result = response.json()
        status_result = result.get("body", {})
        response_signature = result.get("head", {}).get("signature")
        if response_signature and not PaytmChecksum.verifySignature(status_result, merchant_key, response_signature):
            raise ValueError("Invalid transaction status signature")
        amount_matches = Decimal(str(status_result.get("txnAmount", "0"))) == Decimal(order["amount"])
        success = (
            status_result.get("orderId") == order["id"]
            and status_result.get("mid") == mid
            and amount_matches
            and status_result.get("resultInfo", {}).get("resultStatus") == "TXN_SUCCESS"
        )
        update_order(order["id"], status="success" if success else "failed", provider_id=status_result.get("txnId"))
        order = get_order(order["id"])
        return render_template(
            "payment_result.html", order=order, success=success,
            message="Paytm sandbox payment successful." if success else "Paytm reports that this payment did not succeed.",
        )
    except (requests.RequestException, ValueError, InvalidOperation, KeyError, TypeError):
        update_order(order["id"], status="failed")
        order = get_order(order["id"])
        return render_template("payment_result.html", order=order, success=False, message="Unable to verify the Paytm transaction."), 502


@app.route("/food-order", methods=["GET", "POST"])
def food_order():
    if request.method == "GET":
        return render_template("food_order.html")
    try:
        name, email, dish, amount = parse_form_order("Veggie bowl")
    except ValueError as exc:
        flash(str(exc), "error")
        return render_template("food_order.html"), 400
    stripe_key = os.environ.get("STRIPE_SECRET_KEY", "")
    if not stripe_key:
        flash("Stripe test mode is not configured. Add STRIPE_SECRET_KEY to .env.", "error")
        return render_template("food_order.html"), 503
    stripe.api_key = stripe_key
    order_id = create_order("stripe", name, email, dish, amount, "USD")
    try:
        checkout = stripe.checkout.Session.create(
            mode="payment",
            customer_email=email,
            client_reference_id=order_id,
            metadata={"local_order_id": order_id},
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": dish},
                    "unit_amount": int(amount * 100),
                },
                "quantity": 1,
            }],
            success_url=f"{payment_url('stripe_success')}?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=payment_url("stripe_cancel", order_id=order_id),
        )
        update_order(order_id, status="pending", provider_id=checkout.id)
        return redirect(checkout.url, code=303)
    except stripe.StripeError:
        update_order(order_id, status="failed")
        flash("Stripe could not start checkout. Check your test key and try again.", "error")
        return render_template("food_order.html"), 502


@app.get("/stripe/success")
def stripe_success():
    session_id = request.args.get("session_id", "")
    stripe_key = os.environ.get("STRIPE_SECRET_KEY", "")
    if not stripe_key or not session_id:
        abort(400)
    stripe.api_key = stripe_key
    try:
        checkout = stripe.checkout.Session.retrieve(session_id)
    except stripe.StripeError:
        abort(502)
    order_id = checkout.get("metadata", {}).get("local_order_id")
    order = get_order(order_id or "", "stripe")
    if not order or checkout.get("client_reference_id") != order["id"]:
        abort(404)
    paid = (
        checkout.get("payment_status") == "paid"
        and checkout.get("currency") == order["currency"].lower()
        and checkout.get("amount_total") == int(Decimal(order["amount"]) * 100)
    )
    update_order(order["id"], status="success" if paid else "failed", provider_id=checkout.id)
    order = get_order(order["id"])
    return render_template(
        "payment_result.html", order=order, success=paid,
        message="Stripe test payment successful." if paid else "Stripe did not confirm a completed payment.",
    )


@app.get("/stripe/cancel/<order_id>")
def stripe_cancel(order_id):
    order = get_order(order_id, "stripe")
    if not order:
        abort(404)
    if order["status"] == "pending":
        update_order(order_id, status="cancelled")
    return render_template("payment_result.html", order=get_order(order_id), success=False, message="Checkout was cancelled.")


def paypal_access_token():
    client_id = os.environ.get("PAYPAL_CLIENT_ID", "")
    client_secret = os.environ.get("PAYPAL_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise RuntimeError("PayPal sandbox credentials are missing.")
    response = requests.post(
        f"{PAYPAL_API}/v1/oauth2/token",
        auth=(client_id, client_secret),
        data={"grant_type": "client_credentials"},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()["access_token"]


@app.route("/paypal/pay", methods=["GET", "POST"])
def paypal_pay():
    if request.method == "GET":
        return render_template("paypal_form.html")
    try:
        name, email, _item, amount = parse_form_order("IPL match tickets")
        token = paypal_access_token()
        local_order_id = create_order("paypal", name, email, "IPL match tickets", amount, "USD")
        response = requests.post(
            f"{PAYPAL_API}/v2/checkout/orders",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "intent": "CAPTURE",
                "purchase_units": [{
                    "reference_id": local_order_id,
                    "custom_id": local_order_id,
                    "description": "IPL match tickets",
                    "amount": {"currency_code": "USD", "value": f"{amount:.2f}"},
                }],
                "application_context": {
                    "return_url": payment_url("paypal_callback"),
                    "cancel_url": payment_url("paypal_cancel", order_id=local_order_id),
                },
            },
            timeout=25,
        )
        response.raise_for_status()
        paypal_order = response.json()
        approval_url = next(link["href"] for link in paypal_order["links"] if link["rel"] == "approve")
        update_order(local_order_id, status="pending", provider_id=paypal_order["id"])
        return redirect(approval_url, code=303)
    except ValueError as exc:
        flash(str(exc), "error")
        return render_template("paypal_form.html"), 400
    except (requests.RequestException, RuntimeError, KeyError, StopIteration):
        flash("PayPal sandbox could not start checkout. Check your credentials and try again.", "error")
        return render_template("paypal_form.html"), 502


@app.get("/paypal/callback")
def paypal_callback():
    paypal_order_id = request.args.get("token", "")
    with db_connect() as connection:
        order = connection.execute(
            "SELECT * FROM payment_orders WHERE provider = 'paypal' AND provider_id = ?", (paypal_order_id,)
        ).fetchone()
    if not order:
        abort(404)
    try:
        token = paypal_access_token()
        response = requests.post(
            f"{PAYPAL_API}/v2/checkout/orders/{paypal_order_id}/capture",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Prefer": "return=representation"},
            json={},
            timeout=25,
        )
        response.raise_for_status()
        capture = response.json()
        purchase_unit = capture.get("purchase_units", [{}])[0]
        capture_detail = purchase_unit.get("payments", {}).get("captures", [{}])[0]
        amount = capture_detail.get("amount", {})
        paid = (
            capture.get("status") == "COMPLETED"
            and purchase_unit.get("custom_id") == order["id"]
            and amount.get("currency_code") == order["currency"]
            and Decimal(str(amount.get("value", "0"))) == Decimal(order["amount"])
        )
        update_order(order["id"], status="success" if paid else "failed", provider_id=paypal_order_id)
        order = get_order(order["id"])
        return render_template(
            "payment_result.html", order=order, success=paid,
            message="PayPal sandbox payment successful." if paid else "PayPal did not confirm a completed payment.",
        )
    except (requests.RequestException, RuntimeError, ValueError, KeyError, IndexError, InvalidOperation):
        update_order(order["id"], status="failed", provider_id=paypal_order_id)
        return render_template("payment_result.html", order=get_order(order["id"]), success=False, message="Unable to verify the PayPal transaction."), 502


@app.get("/paypal/cancel/<order_id>")
def paypal_cancel(order_id):
    order = get_order(order_id, "paypal")
    if not order:
        abort(404)
    if order["status"] == "pending":
        update_order(order_id, status="cancelled")
    return render_template("payment_result.html", order=get_order(order_id), success=False, message="PayPal checkout was cancelled.")


# ChatGPT prompt and adapted initial draft for task 5:
# Prompt: "Write a Flask route for IPL ticket checkout using PayPal sandbox Orders API.
# Validate the server-side amount, create a CAPTURE order, redirect for approval, capture
# it on return, and verify status and amount before showing success. Keep credentials in env vars."
# Draft idea:
# @app.post("/paypal/pay")
# def create_paypal_order():
#     token = paypal_access_token()
#     response = requests.post(f"{PAYPAL_API}/v2/checkout/orders", headers=auth(token), json=order_body)
#     return redirect(next(link["href"] for link in response.json()["links"] if link["rel"] == "approve"))
# Reviewed adaptation persists a local pending order and only marks it paid after the
# server-side capture response matches the order id, currency, amount, and COMPLETED status.


init_db()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PAYMENTS_PORT", "5001")), debug=False)
