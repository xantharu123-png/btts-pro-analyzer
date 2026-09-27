from django.urls import path, re_path, include
from members import views

localized = [
    path("", views.home, name="home"),
    path("register/", views.register, name="register"),
    path("login/", views.login, name="login"),
    path("logout/", views.logout, name="logout"),
    path("account/", views.account, name="account"),
    path("activate/<str:uid>/<str:token>/", views.activate, name="activate"),
    path("password/reset/", views.reset, name="reset"),
    path("password/reset/<str:uid>/<str:token>/", views.reset_confirm, name="reset_confirm"),
    path("checkout/", views.checkout, name="checkout"),
    path("billing/", views.manage, name="manage"),
]
urlpatterns = [
    path("", views.root),
    path("billing/stripe/webhook/", views.webhook, name="stripe_webhook"),
    path("internal/access/", views.internal_access),
    path("health/", views.health),
    re_path(r"^(?P<lang>de|en)/", include(localized)),
]
