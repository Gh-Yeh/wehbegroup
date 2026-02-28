from django.urls import path
from . import views

urlpatterns = [
    path("", views.category_list, name="category_list"),
    path("<int:category_id>/", views.item_list, name="item_list"),
    path("<int:category_id>/pdf/", views.item_list_pdf, name="item_list_pdf"),
    # The New "Edit Desk"
    path("edit-item/<int:item_id>/", views.edit_item, name="edit_item"),
    # The New "Duplicate Desk"
    path(
        "<int:category_id>/duplicate/",
        views.duplicate_category,
        name="duplicate_category",
    ),
    # --- PHASE 2: POS & ORDER MANAGEMENT ---
    path("toggle-order/", views.toggle_order_mode, name="toggle_order_mode"),
]
