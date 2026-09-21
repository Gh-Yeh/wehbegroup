from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.db.models import Q  # <--- NEW: Imports the Q object for 'OR' queries
from .models import Category, Item, Client, Order, OrderItem, SalesmanProfile, SalesmanPriceOverride


# --- NEW: CUSTOM FILTER FOR BARCODE ---
class HasBarcodeFilter(admin.SimpleListFilter):
    title = "has barcode"
    parameter_name = "has_barcode"

    def lookups(self, request, model_admin):
        return (
            ("yes", "Yes"),
            ("no", "No"),
        )

    def queryset(self, request, queryset):
        if self.value() == "yes":
            # Exclude items where barcode is NULL or an empty string
            return queryset.exclude(Q(barcode__isnull=True) | Q(barcode__exact=""))
        if self.value() == "no":
            # Include items where barcode is NULL or an empty string
            return queryset.filter(Q(barcode__isnull=True) | Q(barcode__exact=""))


# --- PHASE 3: CUSTOM ITEM VIEW FOR BARCODES & STAGING ---
class ItemAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "price",
        "stock_quantity",
        "is_scanned",
        "is_active",
    )

    # Added HasBarcodeFilter to the filters on the right sidebar
    list_filter = ("category", "is_active", HasBarcodeFilter)
    search_fields = ("name", "barcode")

    # This magic line lets you click the checkbox directly from the list view without opening the item!
    list_editable = ("is_active",)

    def is_scanned(self, obj):
        return bool(obj.barcode)

    is_scanned.boolean = True
    is_scanned.short_description = "Has Barcode?"


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


# --- NEW: CLIENT ADMIN VIEW (CRM Ownership) ---
class ClientAdmin(admin.ModelAdmin):
    list_display = ("name", "shop_name", "salesman", "created_at")
    list_filter = ("salesman",)
    search_fields = ("name", "shop_name")


class OrderAdmin(admin.ModelAdmin):
    # --- UPDATED: Added salesman to list_display and list_filter ---
    list_display = ("id", "client", "salesman", "created_at", "delivery_date", "total_price")
    list_filter = ("salesman", "created_at", "delivery_date")
    inlines = [OrderItemInline]


# --- PHASE 6: SALESMAN ADMIN VIEWS ---
class SalesmanPriceOverrideAdmin(admin.ModelAdmin):
    list_display = ("salesman", "item", "custom_price")
    list_filter = ("salesman", "item__category")
    search_fields = ("salesman__username", "item__name", "item__barcode")


admin.site.register(Category)
admin.site.register(Item, ItemAdmin)
admin.site.register(Client, ClientAdmin)  # <--- UPDATED
admin.site.register(Order, OrderAdmin)
admin.site.register(SalesmanProfile)
admin.site.register(SalesmanPriceOverride, SalesmanPriceOverrideAdmin)