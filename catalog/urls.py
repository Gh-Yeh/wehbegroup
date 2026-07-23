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
    # --- PHASE 3: SYNC PORTAL ---
    path("sync-inventory/", views.sync_inventory, name="sync_inventory"),
    # --- PHASE 2: POS & ORDER MANAGEMENT ---
    path("toggle-order/", views.toggle_order_mode, name="toggle_order_mode"),
    path("add-to-ticket/<int:item_id>/", views.add_to_ticket, name="add_to_ticket"),
    path(
        "update-cart-item/<int:item_id>/",
        views.update_cart_item,
        name="update_cart_item",
    ),
    path("checkout/", views.checkout, name="checkout"),
    # --- PHASE 2.5: LIVE SEARCH ---
    path("live-search/", views.live_search, name="live_search"),
    # --- PHASE 2: CLIENT DASHBOARD ---
    path("clients/", views.client_list, name="client_list"),
    path("clients/<int:client_id>/", views.client_detail, name="client_detail"),
    path("orders/<int:order_id>/", views.order_detail, name="order_detail"),
    path("orders/<int:order_id>/pdf/", views.order_pdf, name="order_pdf"),
]
