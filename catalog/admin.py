from django.contrib import admin
from .models import Category, Item, Client, Order, OrderItem


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

    # Added is_active to the filters on the right sidebar
    list_filter = ("category", "is_active")
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


class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "client", "created_at", "delivery_date", "total_price")
    list_filter = ("created_at", "delivery_date")
    inlines = [OrderItemInline]


admin.site.register(Category)
admin.site.register(Item, ItemAdmin)
admin.site.register(Client)
admin.site.register(Order, OrderAdmin)
