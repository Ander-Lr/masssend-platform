from django.contrib import admin

from .models import CreditPack, CreditSpend, CreditWallet, PaymentTransaction


@admin.register(CreditWallet)
class CreditWalletAdmin(admin.ModelAdmin):
    list_display = ("user", "balance", "updated_at")
    search_fields = ("user__username", "user__email")


@admin.register(CreditPack)
class CreditPackAdmin(admin.ModelAdmin):
    list_display = ("name", "credits", "price_usd", "is_active", "display_order")
    list_editable = ("is_active", "display_order")


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ("provider", "provider_reference", "user", "credits", "amount_usd", "status", "created_at")
    list_filter = ("provider", "status")
    search_fields = ("provider_reference", "user__username", "user__email")
    readonly_fields = ("id", "created_at", "updated_at", "raw_response")


@admin.register(CreditSpend)
class CreditSpendAdmin(admin.ModelAdmin):
    list_display = ("user", "amount", "reason", "created_at")
    search_fields = ("user__username",)
