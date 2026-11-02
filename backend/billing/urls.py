from django.urls import path

from .views import catalog_views, checkout_views, wallet_views

urlpatterns = [
    path("packs/", catalog_views.list_packs),
    path("checkout/start/", checkout_views.start_checkout),
    path("checkout/confirm/", checkout_views.confirm_checkout),
    path("wallet/", wallet_views.get_wallet),
    path("wallet/history/", wallet_views.get_history),
]
