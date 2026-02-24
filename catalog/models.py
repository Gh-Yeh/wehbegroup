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

    class Meta:
        # --- THE CHANGE IS HERE ---
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