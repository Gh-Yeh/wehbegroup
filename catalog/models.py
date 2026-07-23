from django.db import models
from PIL import Image


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


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

    class Meta:
        # Now we include 'description' in the uniqueness check.
        # This allows same Name + Category, as long as Description is different.
        unique_together = ("category", "name", "description")

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # 1. Save the file normally first
        super().save(*args, **kwargs)

        # 2. Resize logic
        if self.image:
            # Open the image path
            img_path = self.image.path
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

    class Meta:
        # Prevents adding the exact same person + shop twice
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

    def __str__(self):
        return f"Order #{self.id} - {self.client.name}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    # SET_NULL future-proofs your accounting if an item is ever deleted
    item = models.ForeignKey(Item, on_delete=models.SET_NULL, null=True)
    quantity = models.PositiveIntegerField(default=1)

    # We lock this in at the moment of purchase!
    price_at_order = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        item_name = self.item.name if self.item else "Deleted Item"
        return f"{self.quantity}x {item_name} (Order #{self.order.id})"

    @property
    def total_price(self):
        return self.quantity * self.price_at_order
