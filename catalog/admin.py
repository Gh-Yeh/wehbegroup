from django.contrib import admin
from .models import Category, Item, Client, Order, OrderItem


# --- PHASE 3: CUSTOM ITEM VIEW FOR BARCODES ---
class ItemAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "stock_quantity", "is_scanned")
    list_filter = ("category",)
    search_fields = ("name", "barcode")

    # This creates the visual representation you asked for!
    def is_scanned(self, obj):
        return bool(obj.barcode)

    # This tells Django to use a cool Green Checkmark / Red X icon
    is_scanned.boolean = True
    is_scanned.short_description = "Has Barcode?"


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "client", "created_at", "delivery_date", "total_price")
    list_filter = ("created_at", "delivery_date")
    inlines = [OrderItemInline]


admin.site.register(Category)
admin.site.register(
    Item, ItemAdmin
)  # <--- Replaced standard registration with our custom one
admin.site.register(Client)
admin.site.register(Order, OrderAdmin)
