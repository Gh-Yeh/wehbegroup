from django.contrib import admin
from .models import Category, Item, Client, Order, OrderItem


# This allows us to see the items INSIDE the order page in the admin panel
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "client", "created_at", "delivery_date", "total_price")
    list_filter = ("created_at", "delivery_date")
    inlines = [OrderItemInline]


admin.site.register(Category)
admin.site.register(Item)
admin.site.register(Client)
admin.site.register(Order, OrderAdmin)
