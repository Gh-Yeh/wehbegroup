import os
from django.db import models
from django.contrib.auth.models import User
from PIL import Image


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)

    # --- NEW: Category Background Image ---
    image = models.ImageField(upload_to="categories/", blank=True, null=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # 1. Save the file normally first
        super().save(*args, **kwargs)

        # 2. Resize logic for the background banner
        if self.image:
            img_path = self.image.path

            # Check if the file physically exists before opening
            if os.path.exists(img_path):
                img = Image.open(img_path)

                # Limit to 800x600 for landscape background banners
                if img.height > 600 or img.width > 800:
                    output_size = (800, 600)
                    img.thumbnail(output_size)
                    # Save it back to the same path, compressed
                    img.save(img_path, quality=70)


class Item(models.Model):
    name = models.CharField(max_length=200)

    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="items"
    )
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to="products/", blank=True, null=True)

    # --- PHASE 3: INVENTORY ENGINE FIELDS ---
    barcode = models.CharField(max_length=100, blank=True, null=True, unique=True)
    stock_quantity = models.IntegerField(default=0)

    # --- PHASE 3: THE STAGING LOCK ---
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("category", "name", "description")

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # 1. Save the file normally first
        super().save(*args, **kwargs)

        # 2. Resize logic (WITH NEW GUARDRAIL)
        if self.image:
            img_path = self.image.path

            # Check if the file physically exists before opening
            if os.path.exists(img_path):
                img = Image.open(img_path)

                # Check if it needs resizing
                if img.height > 800 or img.width > 800:
                    output_size = (800, 800)
                    img.thumbnail(output_size)
                    # Save it back to the same path, compressed
                    img.save(img_path, quality=70)


# ==========================================
# PHASE 2: POS & ORDER MANAGEMENT MODELS
# ==========================================

class Client(models.Model):
    name = models.CharField(max_length=200)
    shop_name = models.CharField(max_length=200, blank=True, null=True)
    phone_number = models.CharField(max_length=50, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # --- NEW: CRM Ownership ---
    # Links the client to a specific salesman. If null, it belongs to the Admin.
    salesman = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="clients"
    )

    class Meta:
        unique_together = ("name", "shop_name")

    def __str__(self):
        if self.shop_name:
            return f"{self.name} ({self.shop_name})"
        return self.name


class Order(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="orders")
    created_at = models.DateTimeField(auto_now_add=True)
    delivery_date = models.DateField(blank=True, null=True)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    # --- NEW: CRM Ownership ---
    salesman = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_orders",
    )

    def __str__(self):
        return f"Order #{self.id} - {self.client.name}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    item = models.ForeignKey(Item, on_delete=models.SET_NULL, null=True)
    quantity = models.PositiveIntegerField(default=1)
    price_at_order = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        item_name = self.item.name if self.item else "Deleted Item"
        return f"{self.quantity}x {item_name} (Order #{self.order.id})"

    @property
    def total_price(self):
        return self.quantity * self.price_at_order


# ==========================================
# PHASE 6: SALESMAN PRICING OVERRIDES
# ==========================================

class SalesmanProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='salesman_profile')
    # Default is 1.00 (No change). 1.10 = +10%. 0.90 = -10%.
    global_multiplier = models.DecimalField(max_digits=5, decimal_places=2, default=1.00)

    def __str__(self):
        return f"{self.user.username} Profile"


class SalesmanPriceOverride(models.Model):
    salesman = models.ForeignKey(User, on_delete=models.CASCADE, related_name='price_overrides')
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='overrides')
    custom_price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        # Prevents a single salesman from having multiple conflicting overrides for the same item
        unique_together = ('salesman', 'item')

    def __str__(self):
        return f"{self.salesman.username} - {self.item.name}: ${self.custom_price}"