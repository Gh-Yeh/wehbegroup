from django.urls import path
from . import views

urlpatterns = [
    path("", views.category_list, name="category_list"),
    path("<int:category_id>/", views.item_list, name="item_list"),
    path("<int:category_id>/pdf/", views.item_list_pdf, name="item_list_pdf"),
    path("edit-item/<int:item_id>/", views.edit_item, name="edit_item"),
    path(
        "<int:category_id>/duplicate/",
        views.duplicate_category,
        name="duplicate_category",
    ),
    # --- PHASE 2: POS & ORDER MANAGEMENT ---
    path("toggle-order/", views.toggle_order_mode, name="toggle_order_mode"),
    path("add-to-ticket/<int:item_id>/", views.add_to_ticket, name="add_to_ticket"),
    path(
        "update-cart-item/<int:item_id>/",
        views.update_cart_item,
        name="update_cart_item",
    ),
]
