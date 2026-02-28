from datetime import datetime
from decimal import Decimal
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q
from django.db.models.functions import Lower
from django.contrib.auth.decorators import login_required

from .models import Category, Item, Client, Order, OrderItem
from .forms import ItemForm
from .utils import render_to_pdf


def category_list(request):
    is_ordering = request.session.get("is_ordering", False)
    query = request.GET.get("q")

    if query:
        items = Item.objects.filter(
            Q(name__icontains=query) | Q(description__icontains=query)
        ).order_by(Lower("name"))

        return render(
            request,
            "catalog/item_list.html",
            {
                "items": items,
                "search_query": query,
                "category": None,
                "is_ordering": is_ordering,
            },
        )
    else:
        categories = Category.objects.all()
        return render(
            request,
            "catalog/category_list.html",
            {"categories": categories, "is_ordering": is_ordering},
        )


def item_list(request, category_id):
    is_ordering = request.session.get("is_ordering", False)
    category = get_object_or_404(Category, id=category_id)
    items = category.items.all().order_by(Lower("name"))

    cart = request.session.get("ticket_cart", {})
    cart_items = []
    cart_item_ids = []

    if is_ordering:
        for item_id_str, qty in cart.items():
            try:
                cart_item = Item.objects.get(id=int(item_id_str))
                cart_items.append({"item": cart_item, "quantity": qty})
                cart_item_ids.append(cart_item.id)
            except Item.DoesNotExist:
                pass

    return render(
        request,
        "catalog/item_list.html",
        {
            "category": category,
            "items": items,
            "is_ordering": is_ordering,
            "cart_items": cart_items,
            "cart_item_ids": cart_item_ids,
        },
    )


def item_list_pdf(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    items = category.items.all().order_by(Lower("name"))

    context = {
        "category": category,
        "items": items,
        "pagesize": "A4",
    }

    pdf = render_to_pdf("catalog/pdf_template.html", context)

    if pdf:
        response = HttpResponse(pdf, content_type="application/pdf")
        current_date = datetime.now().strftime("%Y-%m-%d")
        filename = f"{category.name}_{current_date}.pdf"

        content = f"attachment; filename={filename}"
        response["Content-Disposition"] = content
        return response

    return HttpResponse("Not found")


@login_required
def edit_item(request, item_id):
    item = get_object_or_404(Item, id=item_id)

    if request.method == "POST":
        form = ItemForm(request.POST, request.FILES, instance=item)
        if form.is_valid():
            form.save()
            if item.category:
                return redirect("item_list", category_id=item.category.id)
            else:
                return redirect("category_list")
    else:
        form = ItemForm(instance=item)

    return render(request, "catalog/edit_item.html", {"form": form, "item": item})


@login_required
def duplicate_category(request, category_id):
    original_category = get_object_or_404(Category, id=category_id)

    if request.method == "POST":
        new_name = request.POST.get("new_name")
        try:
            percentage = Decimal(request.POST.get("percentage", 0))
        except:
            percentage = Decimal(0)

        try:
            new_category = Category.objects.create(name=new_name)
        except:
            return HttpResponse(
                f"Error: A category named '{new_name}' already exists. Please go back and choose a different name."
            )

        old_items = original_category.items.all().order_by(Lower("name"))

        for item in old_items:
            factor = 1 + (percentage / 100)
            new_price = item.price * factor

            Item.objects.create(
                category=new_category,
                name=item.name,
                description=item.description,
                price=new_price,
                image=item.image,
            )

        return redirect("item_list", category_id=new_category.id)

    return render(
        request, "catalog/duplicate_category.html", {"category": original_category}
    )


# ==========================================
# PHASE 2: POS & ORDER MANAGEMENT VIEWS
# ==========================================
@login_required
def toggle_order_mode(request):
    current_state = request.session.get("is_ordering", False)
    request.session["is_ordering"] = not current_state

    if current_state == True:
        request.session["ticket_cart"] = {}

    return redirect("category_list")


@login_required
def add_to_ticket(request, item_id):
    if request.method == "POST":
        item = get_object_or_404(Item, id=item_id)
        quantity = int(request.POST.get("quantity", 1))

        cart = request.session.get("ticket_cart", {})
        item_id_str = str(item_id)

        if item_id_str in cart:
            cart[item_id_str] += quantity
        else:
            cart[item_id_str] = quantity

        request.session["ticket_cart"] = cart

        if item.category:
            return redirect("item_list", category_id=item.category.id)

    return redirect("category_list")


@login_required
def update_cart_item(request, item_id):
    if request.method == "POST":
        cart = request.session.get("ticket_cart", {})
        item_id_str = str(item_id)
        action = request.POST.get("action")

        if action == "remove":
            if item_id_str in cart:
                del cart[item_id_str]

        elif action == "update":
            new_qty = int(request.POST.get("quantity", 1))
            if new_qty > 0:
                cart[item_id_str] = new_qty
            else:
                if item_id_str in cart:
                    del cart[item_id_str]

        request.session["ticket_cart"] = cart
        return redirect(request.META.get("HTTP_REFERER", "category_list"))


@login_required
def checkout(request):
    cart = request.session.get("ticket_cart", {})

    if not cart:
        return redirect("category_list")

    cart_items = []
    cart_total = Decimal(0)

    for item_id_str, qty in cart.items():
        try:
            item = Item.objects.get(id=int(item_id_str))
            total_item_price = item.price * qty
            cart_items.append(
                {"item": item, "quantity": qty, "total_price": total_item_price}
            )
            cart_total += total_item_price
        except Item.DoesNotExist:
            pass

    if request.method == "POST":
        client_id = request.POST.get("client_id")

        if client_id:
            client = get_object_or_404(Client, id=client_id)
        else:
            new_name = request.POST.get("new_client_name")
            new_shop = request.POST.get("new_client_shop")
            new_phone = request.POST.get("new_client_phone")
            new_address = request.POST.get("new_client_address")

            client, created = Client.objects.get_or_create(
                name=new_name,
                shop_name=new_shop,
                defaults={"phone_number": new_phone, "address": new_address},
            )

        delivery_date = request.POST.get("delivery_date") or None
        order = Order.objects.create(
            client=client,
            delivery_date=delivery_date,
            total_price=0,
        )

        actual_total = Decimal(0)
        for c_item in cart_items:
            OrderItem.objects.create(
                order=order,
                item=c_item["item"],
                quantity=c_item["quantity"],
                price_at_order=c_item["item"].price,
            )
            actual_total += c_item["item"].price * c_item["quantity"]

        order.total_price = actual_total
        order.save()

        request.session["ticket_cart"] = {}
        request.session["is_ordering"] = False

        # --- PHASE 2: Redirect to the Client's page after saving! ---
        return redirect("client_detail", client_id=client.id)

    clients = Client.objects.all().order_by("name")

    return render(
        request,
        "catalog/checkout.html",
        {"cart_items": cart_items, "cart_total": cart_total, "clients": clients},
    )


# ==========================================
# PHASE 2: CLIENT DASHBOARD VIEWS
# ==========================================


@login_required
def client_list(request):
    # Get all clients alphabetically
    clients = Client.objects.all().order_by("name")
    return render(request, "catalog/client_list.html", {"clients": clients})


@login_required
def client_detail(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    # Get all orders for this client, newest first
    orders = client.orders.all().order_by("-created_at")

    return render(
        request, "catalog/client_detail.html", {"client": client, "orders": orders}
    )


@login_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    order_items = order.items.all()

    return render(
        request,
        "catalog/order_detail.html",
        {"order": order, "order_items": order_items},
    )
