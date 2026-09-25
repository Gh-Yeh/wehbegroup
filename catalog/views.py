import os
import openpyxl
from datetime import datetime
from decimal import Decimal
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q, Sum
from django.db.models.functions import Lower
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User, Group
from django.contrib import messages
from django.db import IntegrityError, transaction

from .models import (
    Category,
    Item,
    Client,
    Order,
    OrderItem,
    SalesmanProfile,
    SalesmanPriceOverride,
)
from .forms import ItemForm
from .utils import render_to_pdf

# ==========================================
# PHASE 6: SALESMAN PRICING ENGINE (HELPERS)
# ==========================================


def get_single_item_price(user, item):
    if not user.is_authenticated or not user.groups.filter(name="Salesman").exists():
        return item.price

    override = SalesmanPriceOverride.objects.filter(salesman=user, item=item).first()
    if override:
        return override.custom_price

    profile = getattr(user, "salesman_profile", None)
    multiplier = profile.global_multiplier if profile else Decimal("1.00")
    return round(item.price * multiplier, 2)


def apply_salesman_prices(user, items_queryset):
    items = list(items_queryset)
    if not user.is_authenticated or not user.groups.filter(name="Salesman").exists():
        return items

    profile = getattr(user, "salesman_profile", None)
    multiplier = profile.global_multiplier if profile else Decimal("1.00")

    overrides = SalesmanPriceOverride.objects.filter(salesman=user, item__in=items)
    override_dict = {o.item_id: o.custom_price for o in overrides}

    for item in items:
        if item.id in override_dict:
            item.price = override_dict[item.id]
        else:
            item.price = round(item.price * multiplier, 2)

    return items


def get_salesman_margin_percentage(user):
    """Calculates the current margin percentage to display in the HTML UI"""
    if not user.is_authenticated or not user.groups.filter(name="Salesman").exists():
        return 0
    profile = getattr(user, "salesman_profile", None)
    if profile:
        multiplier = profile.global_multiplier
        val = (multiplier - Decimal("1.00")) * Decimal("100.00")
        return val.normalize()
    return 0


# ==========================================
# MAIN VIEWS
# ==========================================


def category_list(request):
    query = request.GET.get("q")

    if (
        not query
        and request.user.is_authenticated
        and request.user.groups.filter(name="Salesman").exists()
    ):
        return redirect("all_items")

    is_ordering = request.session.get("is_ordering", False)
    cart = request.session.get("ticket_cart", {})
    cart_items = []
    cart_total = Decimal(0)

    if is_ordering:
        for item_id_str, qty in cart.items():
            try:
                cart_item = Item.objects.get(id=int(item_id_str))
                cart_item.price = get_single_item_price(request.user, cart_item)
                item_total = cart_item.price * qty
                cart_items.append(
                    {
                        "item": cart_item,
                        "quantity": qty,
                        "total_price": item_total,
                    }
                )
                cart_total += item_total
            except Item.DoesNotExist:
                pass

    context = {
        "is_ordering": is_ordering,
        "cart_items": cart_items,
        "cart_total": cart_total,
        "current_margin": get_salesman_margin_percentage(request.user),
    }

    if query:
        items_qs = Item.objects.filter(
            (Q(name__icontains=query) | Q(description__icontains=query))
            & Q(is_active=True)
        ).order_by(Lower("name"))

        items = apply_salesman_prices(request.user, items_qs)
        context.update({"items": items, "search_query": query, "category": None})
        return render(request, "catalog/item_list.html", context)
    else:
        categories = Category.objects.all()
        context.update({"categories": categories})
        return render(request, "catalog/category_list.html", context)


def all_items(request):
    is_ordering = request.session.get("is_ordering", False)

    items_qs = Item.objects.filter(is_active=True).order_by(Lower("name"))
    items = apply_salesman_prices(request.user, items_qs)

    cart = request.session.get("ticket_cart", {})
    cart_items = []
    cart_item_ids = []
    cart_total = Decimal(0)

    if is_ordering:
        for item_id_str, qty in cart.items():
            try:
                cart_item = Item.objects.get(id=int(item_id_str))
                cart_item.price = get_single_item_price(request.user, cart_item)
                item_total = cart_item.price * qty
                cart_items.append(
                    {
                        "item": cart_item,
                        "quantity": qty,
                        "total_price": item_total,
                    }
                )
                cart_item_ids.append(cart_item.id)
                cart_total += item_total
            except Item.DoesNotExist:
                pass

    return render(
        request,
        "catalog/item_list.html",
        {
            "category": None,
            "items": items,
            "is_ordering": is_ordering,
            "cart_items": cart_items,
            "cart_item_ids": cart_item_ids,
            "cart_total": cart_total,
            "is_all_items_view": True,
            "current_margin": get_salesman_margin_percentage(request.user),
        },
    )


def item_list(request, category_id):
    is_ordering = request.session.get("is_ordering", False)
    category = get_object_or_404(Category, id=category_id)

    if request.user.is_authenticated and category.name == "Uncategorized":
        items_qs = category.items.all().order_by(Lower("name"))
    else:
        items_qs = category.items.filter(is_active=True).order_by(Lower("name"))

    items = apply_salesman_prices(request.user, items_qs)

    cart = request.session.get("ticket_cart", {})
    cart_items = []
    cart_item_ids = []
    cart_total = Decimal(0)

    if is_ordering:
        for item_id_str, qty in cart.items():
            try:
                cart_item = Item.objects.get(id=int(item_id_str))
                cart_item.price = get_single_item_price(request.user, cart_item)
                item_total = cart_item.price * qty
                cart_items.append(
                    {
                        "item": cart_item,
                        "quantity": qty,
                        "total_price": item_total,
                    }
                )
                cart_item_ids.append(cart_item.id)
                cart_total += item_total
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
            "cart_total": cart_total,
            "current_margin": get_salesman_margin_percentage(request.user),
        },
    )


@login_required
def item_list_pdf(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    items_qs = category.items.filter(is_active=True).order_by(Lower("name"))

    items = apply_salesman_prices(request.user, items_qs)

    logo_path = os.path.join(settings.MEDIA_ROOT, "logo.png")

    context = {
        "category": category,
        "items": items,
        "pagesize": "A4",
        "logo_path": logo_path,
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
            updated_item = form.save(commit=False)

            new_cat_name = request.POST.get("new_category_name", "").strip()
            if new_cat_name:
                new_category, created = Category.objects.get_or_create(
                    name=new_cat_name
                )
                updated_item.category = new_category

            if updated_item.category and updated_item.category.name != "Uncategorized":
                updated_item.is_active = True

            merge_item_id = request.POST.get("merge_item_id")
            if merge_item_id:
                try:
                    junk_item = Item.objects.get(id=merge_item_id)
                    updated_item.barcode = junk_item.barcode
                    updated_item.stock_quantity = junk_item.stock_quantity
                    updated_item.price = junk_item.price
                    junk_item.delete()
                except Item.DoesNotExist:
                    pass

            updated_item.save()

            if updated_item.category:
                return redirect("item_list", category_id=updated_item.category.id)
            else:
                return redirect("category_list")
    else:
        form = ItemForm(instance=item)

    suggestions = []

    if not item.barcode:
        words = [word for word in item.name.split() if len(word) > 1]

        if words:
            strict_query = Q()
            for word in words[:2]:
                strict_query &= Q(name__icontains=word)

            strict_matches = (
                Item.objects.filter(category__name="Uncategorized", is_active=False)
                .filter(strict_query)
                .exclude(id=item.id)
                .order_by(Lower("name"))
            )

            loose_query = Q()
            for word in words:
                loose_query |= Q(name__icontains=word)

            loose_matches = (
                Item.objects.filter(category__name="Uncategorized", is_active=False)
                .filter(loose_query)
                .exclude(id=item.id)
                .order_by(Lower("name"))
            )

            combined_suggestions = list(strict_matches)
            strict_ids = {match.id for match in strict_matches}

            for match in loose_matches:
                if match.id not in strict_ids:
                    combined_suggestions.append(match)

            suggestions = combined_suggestions[:15]

    return render(
        request,
        "catalog/edit_item.html",
        {"form": form, "item": item, "suggestions": suggestions},
    )


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


@login_required
def edit_category_image(request, category_id):
    if not request.user.is_staff:
        messages.error(
            request, "Access Denied: Only administrators can update category images."
        )
        return redirect("category_list")

    category = get_object_or_404(Category, id=category_id)

    if request.method == "POST":
        new_image = request.FILES.get("category_image")

        if new_image:
            category.image = new_image
            category.save()
            messages.success(
                request, f"Background image updated successfully for '{category.name}'!"
            )
        else:
            messages.error(request, "No image file was selected.")

    return redirect("category_list")


# ==========================================
# PHASE 3: THE SYNC PORTAL ENGINE
# ==========================================
@login_required
def sync_inventory(request):
    if not request.user.is_staff:
        return redirect("category_list")

    if request.method == "POST":
        excel_file = request.FILES.get("excel_file")
        reset_salesman_prices = request.POST.get("reset_salesman_prices") == "on"

        if not excel_file:
            messages.error(request, "Please select a file to upload.")
            return redirect("sync_inventory")
        if not excel_file.name.endswith(".xlsx"):
            messages.error(request, "Invalid format. Please upload an .xlsx file.")
            return redirect("sync_inventory")

        current_row_number = 1
        current_processing_barcode = "N/A"

        try:
            with transaction.atomic():
                if reset_salesman_prices:
                    SalesmanPriceOverride.objects.all().delete()
                    SalesmanProfile.objects.update(global_multiplier=Decimal("1.00"))

                uncategorized_folder, created = Category.objects.get_or_create(
                    name="Uncategorized"
                )

                wb = openpyxl.load_workbook(excel_file, data_only=True)
                sheet = wb.active

                rows = list(sheet.iter_rows(values_only=True))
                if len(rows) < 2:
                    messages.error(
                        request, "The uploaded file is empty or missing data."
                    )
                    return redirect("sync_inventory")

                headers = [str(col).upper().strip() if col else "" for col in rows[0]]

                # Helper to match column headers across changing FoxPro exports
                def get_column_index(candidates, header_list):
                    for name in candidates:
                        if name in header_list:
                            return header_list.index(name)
                    return None

                code_idx = get_column_index(["CODE", "BARCODE"], headers)
                item_idx = get_column_index(["ITEM", "NAME", "DESCRIPTION"], headers)
                qtnet_idx = get_column_index(["QTNET", "STOCK", "QTY", "QUANTITY"], headers)
                salepr_idx = get_column_index(
                    ["SALE_PRICE", "SALEPR", "SALE_PRICESALE_PRICE", "SALE PRICE", "PRICE"],
                    headers,
                )

                if (
                    code_idx is None
                    or item_idx is None
                    or qtnet_idx is None
                    or salepr_idx is None
                ):
                    missing = []
                    if code_idx is None:
                        missing.append("CODE")
                    if item_idx is None:
                        missing.append("ITEM")
                    if qtnet_idx is None:
                        missing.append("QTNET")
                    if salepr_idx is None:
                        missing.append("SALE_PRICE/SALEPR")
                    messages.error(
                        request,
                        f"Missing required columns: {', '.join(missing)}. Please verify the Excel headers.",
                    )
                    return redirect("sync_inventory")

                items_updated = 0
                synced_barcodes = []
                processed_barcodes = set()

                for idx, row in enumerate(rows[1:], start=2):
                    current_row_number = idx

                    raw_code = (
                        str(row[code_idx]).strip() if row[code_idx] is not None else ""
                    )
                    current_processing_barcode = raw_code if raw_code else "No Barcode"

                    raw_name = (
                        str(row[item_idx]).strip()
                        if row[item_idx] is not None
                        else "Unknown Item"
                    )
                    raw_qtnet = row[qtnet_idx]
                    raw_salepr = row[salepr_idx]

                    if not raw_code:
                        continue

                    if raw_code in processed_barcodes:
                        continue

                    processed_barcodes.add(raw_code)
                    synced_barcodes.append(raw_code)

                    try:
                        stock = int(float(raw_qtnet)) if raw_qtnet is not None else 0
                    except ValueError:
                        stock = 0

                    try:
                        raw_val = str(raw_salepr) if raw_salepr is not None else "0.00"
                        price = round(Decimal(raw_val), 2)
                    except:
                        price = Decimal("0.00")

                    item = Item.objects.filter(barcode=raw_code).first()

                    if item:
                        item_changed = False

                        if item.stock_quantity != stock:
                            item.stock_quantity = stock
                            item_changed = True

                        if item.price != price:
                            item.price = price
                            item_changed = True

                        if item_changed:
                            item.save(update_fields=["stock_quantity", "price"])
                            if item.is_active:
                                items_updated += 1
                    else:
                        # Isolated Savepoint 1
                        try:
                            with transaction.atomic():
                                Item.objects.create(
                                    name=raw_name,
                                    category=uncategorized_folder,
                                    barcode=raw_code,
                                    stock_quantity=stock,
                                    price=price,
                                    is_active=False,
                                )
                        except IntegrityError:
                            # Isolated Savepoint 2: Duplicate name fallback
                            try:
                                with transaction.atomic():
                                    Item.objects.create(
                                        name=f"{raw_name} ({raw_code})",
                                        category=uncategorized_folder,
                                        barcode=raw_code,
                                        stock_quantity=stock,
                                        price=price,
                                        is_active=False,
                                    )
                            except IntegrityError:
                                pass

                uncategorized_folder.items.exclude(barcode__in=synced_barcodes).delete()
                uncategorized_count = uncategorized_folder.items.count()

                success_msg = f"🚀 Sync Complete! {items_updated} items updated. {uncategorized_count} sitting in 'Uncategorized'."
                if reset_salesman_prices:
                    success_msg += " ⚠️ All Salesman Custom Prices were successfully WIPED and reset to default."

                messages.success(request, success_msg)

        except Exception as e:
            error_message = f"Crash detected at Row {current_row_number} (Barcode: {current_processing_barcode}). System Error: {str(e)}"
            messages.error(request, error_message)

        return redirect("sync_inventory")

    return render(request, "catalog/upload_inventory.html")


# ==========================================
# PHASE 2: POS & ORDER MANAGEMENT VIEWS
# ==========================================
@login_required
def toggle_order_mode(request):
    if request.method == "POST":
        current_state = request.session.get("is_ordering", False)
        request.session["is_ordering"] = not current_state

        if current_state == True:
            request.session["ticket_cart"] = {}

    if request.user.groups.filter(name="Salesman").exists():
        return redirect("all_items")
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

        if request.user.groups.filter(name="Salesman").exists():
            return redirect("all_items")
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
    is_salesman = request.user.groups.filter(name="Salesman").exists()
    cart = request.session.get("ticket_cart", {})

    if not cart:
        if is_salesman:
            return redirect("all_items")
        return redirect("category_list")

    cart_items = []
    cart_total = Decimal(0)

    for item_id_str, qty in cart.items():
        try:
            item = Item.objects.get(id=int(item_id_str))
            item.price = get_single_item_price(request.user, item)
            total_item_price = item.price * qty
            cart_items.append(
                {"item": item, "quantity": qty, "total_price": total_item_price}
            )
            cart_total += total_item_price
        except Item.DoesNotExist:
            pass

    if request.method == "POST":
        client_id = request.POST.get("client_id")

        with transaction.atomic():
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
                    defaults={
                        "phone_number": new_phone,
                        "address": new_address,
                        "salesman": request.user if is_salesman else None,
                    },
                )

            delivery_date = request.POST.get("delivery_date") or None
            order = Order.objects.create(
                client=client,
                delivery_date=delivery_date,
                total_price=0,
                salesman=request.user if is_salesman else None,
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

        return redirect("client_detail", client_id=client.id)

    if is_salesman:
        clients = Client.objects.filter(salesman=request.user).order_by("name")
    else:
        clients = Client.objects.all().order_by("name")

    return render(
        request,
        "catalog/checkout.html",
        {
            "cart_items": cart_items,
            "cart_total": cart_total,
            "clients": clients,
            "current_margin": get_salesman_margin_percentage(request.user),
        },
    )


# ==========================================
# PHASE 2: CLIENT DASHBOARD VIEWS
# ==========================================


@login_required
def client_list(request):
    if request.user.groups.filter(name="Salesman").exists():
        clients = Client.objects.filter(salesman=request.user).order_by("name")
    else:
        clients = Client.objects.all().order_by("name")

    return render(
        request,
        "catalog/client_list.html",
        {
            "clients": clients,
            "current_margin": get_salesman_margin_percentage(request.user),
        },
    )


@login_required
def client_detail(request, client_id):
    client = get_object_or_404(Client, id=client_id)

    if (
        request.user.groups.filter(name="Salesman").exists()
        and client.salesman != request.user
    ):
        messages.error(request, "Access Denied: You can only view your own clients.")
        return redirect("client_list")

    orders_qs = client.orders.all().order_by("created_at")
    orders = []
    for i, order in enumerate(orders_qs, 1):
        order.client_order_number = i
        orders.append(order)
    orders.reverse()
    return render(
        request,
        "catalog/client_detail.html",
        {
            "client": client,
            "orders": orders,
            "current_margin": get_salesman_margin_percentage(request.user),
        },
    )


@login_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    if (
        request.user.groups.filter(name="Salesman").exists()
        and order.salesman != request.user
    ):
        messages.error(request, "Access Denied: You can only view your own orders.")
        return redirect("client_list")

    order_items = order.items.all()
    client_order_number = Order.objects.filter(
        client=order.client, id__lte=order.id
    ).count()
    return render(
        request,
        "catalog/order_detail.html",
        {
            "order": order,
            "order_items": order_items,
            "client_order_number": client_order_number,
            "current_margin": get_salesman_margin_percentage(request.user),
        },
    )


@login_required
def order_pdf(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    if (
        request.user.groups.filter(name="Salesman").exists()
        and order.salesman != request.user
    ):
        return HttpResponse("Access Denied")

    order_items = order.items.all()
    logo_path = os.path.join(settings.MEDIA_ROOT, "logo.png")
    client_order_number = Order.objects.filter(
        client=order.client, id__lte=order.id
    ).count()
    context = {
        "order": order,
        "order_items": order_items,
        "pagesize": "A4",
        "logo_path": logo_path,
        "client_order_number": client_order_number,
    }
    pdf = render_to_pdf("catalog/receipt_pdf_template.html", context)
    if pdf:
        response = HttpResponse(pdf, content_type="application/pdf")
        filename = f"{order.client.name}_#{client_order_number}.pdf"
        content = f'attachment; filename="{filename}"'
        response["Content-Disposition"] = content
        return response
    return HttpResponse("Error generating PDF")


# ==========================================
# PHASE 2.5: LIVE SEARCH API
# ==========================================
def live_search(request):
    query = request.GET.get("q", "")
    results = []

    if query.strip():
        items_qs = Item.objects.filter(
            (Q(name__icontains=query) | Q(description__icontains=query))
            & Q(is_active=True)
        ).order_by(Lower("name"))[:15]

        items = apply_salesman_prices(request.user, items_qs)

        for item in items:
            if item.category:
                results.append(
                    {
                        "id": item.id,
                        "name": item.name,
                        "category_id": item.category.id,
                        "category_name": item.category.name,
                        "price": str(item.price),
                    }
                )

    return JsonResponse({"results": results})


# ==========================================
# PHASE 6: SALESMAN OVERRIDE ACTIONS
# ==========================================
@login_required
def update_salesman_margin(request):
    if (
        request.method == "POST"
        and request.user.groups.filter(name="Salesman").exists()
    ):
        action = request.POST.get("action", "update")

        if action == "reset_all":
            with transaction.atomic():
                SalesmanPriceOverride.objects.filter(salesman=request.user).delete()
                profile, created = SalesmanProfile.objects.get_or_create(
                    user=request.user
                )
                profile.global_multiplier = Decimal("1.00")
                profile.save()
            messages.success(
                request,
                "🚨 Dashboard Reset: All custom prices wiped and margin returned to 0%. You are now seeing Admin base prices.",
            )

        else:
            try:
                percentage = Decimal(request.POST.get("multiplier_percentage", 0))
                multiplier = Decimal("1.00") + (percentage / Decimal("100.00"))

                profile, created = SalesmanProfile.objects.get_or_create(
                    user=request.user
                )
                profile.global_multiplier = multiplier
                profile.save()

                messages.success(
                    request,
                    f"Global margin updated! All base prices shifted by {percentage:g}%",
                )
            except Exception as e:
                messages.error(request, "Invalid margin value.")

    return redirect(request.META.get("HTTP_REFERER", "all_items"))


@login_required
def override_item_price(request, item_id):
    if (
        request.method == "POST"
        and request.user.groups.filter(name="Salesman").exists()
    ):
        item = get_object_or_404(Item, id=item_id)
        action = request.POST.get("action")

        if action == "set":
            try:
                custom_price = Decimal(request.POST.get("custom_price"))
                SalesmanPriceOverride.objects.update_or_create(
                    salesman=request.user,
                    item=item,
                    defaults={"custom_price": custom_price},
                )
                messages.success(
                    request,
                    f"Saved: {item.name} is manually priced at ${custom_price}.",
                )
            except:
                messages.error(request, "Invalid price format.")

        elif action == "reset_to_margin":
            SalesmanPriceOverride.objects.filter(
                salesman=request.user, item=item
            ).delete()
            current_margin = get_salesman_margin_percentage(request.user)
            messages.success(
                request,
                f"Updated: {item.name} is now following your global margin ({current_margin:g}%).",
            )

        elif action == "reset_to_main":
            SalesmanPriceOverride.objects.update_or_create(
                salesman=request.user,
                item=item,
                defaults={"custom_price": item.price},
            )
            messages.success(
                request,
                f"Admin Price Locked: {item.name} is locked to the master price (${item.price}).",
            )

    return redirect(request.META.get("HTTP_REFERER", "all_items"))


# ==========================================
# PHASE 7: ADMIN COMMAND CENTER
# ==========================================
@login_required
def salesman_dashboard(request):
    if not request.user.is_superuser:
        messages.error(
            request, "Access Denied: Only administrators can view the Command Center."
        )
        return redirect("category_list")

    salesmen_users = User.objects.filter(groups__name="Salesman").order_by("username")

    dashboard_data = []
    for salesman in salesmen_users:
        client_count = salesman.clients.count()
        order_count = salesman.sales_orders.count()

        revenue_dict = salesman.sales_orders.aggregate(Sum("total_price"))
        raw_revenue = revenue_dict["total_price__sum"] or Decimal("0.00")
        total_revenue = round(raw_revenue, 2)

        profile = getattr(salesman, "salesman_profile", None)
        current_margin = 0
        if profile:
            multiplier = profile.global_multiplier
            val = (multiplier - Decimal("1.00")) * Decimal("100.00")
            current_margin = val.normalize()

        dashboard_data.append(
            {
                "user": salesman,
                "client_count": client_count,
                "order_count": order_count,
                "total_revenue": total_revenue,
                "current_margin": current_margin,
            }
        )

    return render(
        request,
        "catalog/salesman_dashboard.html",
        {"dashboard_data": dashboard_data},
    )


@login_required
def add_salesman(request):
    if not request.user.is_superuser:
        messages.error(
            request, "Access Denied: Only administrators can create accounts."
        )
        return redirect("category_list")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        first_name = request.POST.get("first_name", "").strip()
        password = request.POST.get("password", "")

        if not username or not password:
            messages.error(request, "Username and Password are required.")
            return redirect("salesman_dashboard")

        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=username,
                    password=password,
                    first_name=first_name,
                    is_staff=True,
                )

                salesman_group, created = Group.objects.get_or_create(name="Salesman")
                user.groups.add(salesman_group)

                SalesmanProfile.objects.create(
                    user=user,
                    global_multiplier=Decimal("1.00"),
                )

            messages.success(
                request,
                f"🎉 Success! Employee '{username}' has been generated and is ready to login.",
            )

        except IntegrityError:
            messages.error(
                request,
                f"Error: The username '{username}' is already taken. Please try a different login ID.",
            )
        except Exception as e:
            messages.error(request, f"System Error: {str(e)}")

    return redirect("salesman_dashboard")