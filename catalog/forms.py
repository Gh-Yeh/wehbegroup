from django import forms
from .models import Item


class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        # Added barcode and stock_quantity to the fields list
        fields = [
            "name",
            "category",
            "description",
            "price",
            "barcode",
            "stock_quantity",
            "image",
        ]

        # This makes the form look pretty (Bootstrap styles)
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "category": forms.Select(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "price": forms.NumberInput(attrs={"class": "form-control"}),
            # --- PHASE 3 ---
            "barcode": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Click here and scan item...",
                }
            ),
            "stock_quantity": forms.NumberInput(attrs={"class": "form-control"}),
            "image": forms.FileInput(attrs={"class": "form-control"}),
        }
