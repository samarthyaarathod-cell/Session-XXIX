from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("signup/", views.signup, name="signup"),
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("welcome/", views.welcome, name="welcome"),
    path("dashboard/", views.dashboard_router, name="dashboard_router"),
    path("dashboard/seller/", views.seller_dashboard, name="seller_dashboard"),
    path("dashboard/buyer/", views.buyer_dashboard, name="buyer_dashboard"),
    path("my-orders/", views.my_orders_view, name="my_orders"),
    path("profile/", views.profile_view, name="profile"),
    path("profile/edit/", views.profile_edit_view, name="profile_edit"),
    path("profile/send-sms-otp/", views.send_sms_otp_view, name="send_sms_otp"),
    path("profile/verify-sms-otp/", views.verify_sms_otp_view, name="verify_sms_otp"),
    path("products/", views.product_list_view, name="product_list"),
    path("restaurants/", views.restaurant_search_view, name="restaurant_search"),
    path("movies/review-counts/", views.movie_review_counts_view, name="movie_review_counts"),
    path("restaurant-location/", views.show_restaurant_location, name="show_restaurant_location"),
    path("pickup-points/", views.search_by_distance, name="search_by_distance"),
    path("products/add/", views.product_create_view, name="product_add"),
    path("products/<int:pk>/edit/", views.product_edit_view, name="product_edit"),
    path("products/<int:pk>/delete/", views.product_delete_view, name="product_delete"),
    path("products/<int:pk>/delete-ajax/", views.product_delete_ajax_view, name="product_delete_ajax"),
    path("ajax-demos/", views.ajax_demos_view, name="ajax_demos"),
    path("ajax-demos/<str:kind>/<str:item_id>/delete/", views.delete_demo_item_view, name="delete_demo_item"),
    path("password-reset-email/", views.send_password_reset_email, name="send_password_reset_email"),
    path("forgot-password/", views.forgot_password_view, name="forgot_password"),
    path("verify-otp/", views.verify_otp_view, name="verify_otp"),
    path("order-confirmation/", views.send_order_confirmation, name="send_order_confirmation"),
    path("ipl-welcome-email/", views.send_ipl_welcome_email, name="send_ipl_welcome_email"),
]
