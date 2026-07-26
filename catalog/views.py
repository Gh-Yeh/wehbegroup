import os
import openpyxl
from datetime import datetime
from decimal import Decimal
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q
from django.db.models.functions import Lower
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import IntegrityError

from .models import Category, Item, Client, Order, OrderItem
from .forms import ItemForm
from .utils import render_to_pdf


def category_list(request):
    is_ordering = request.session.get("is_ordering", False)
    query = request.GET.get("q")

    cart = request.session.get("ticket_cart", {})
    cart_items = []
    cart_total = Decimal(0)

    if is_ordering:
        for item_id_str, qty in cart.items():
            try:
                cart_item = Item.objects.get(id=int(item_id_str))
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

    if query:
        items = Item.objects.filter(
            (Q(name__icontains=query) | Q(description__icontains=query))
            & Q(is_active=True)
        ).order_by(Lower("name"))

        return render(
            request,
            "catalog/item_list.html",
            {
                "items": items,
                "search_query": query,
                "category": None,
                "is_ordering": is_ordering,
                "cart_items": cart_items,
                "cart_total": cart_total,
            },
        )
    else:
        categories = Category.objects.all()
        return render(
            request,
            "catalog/category_list.html",
            {
                "categories": categories,
                "is_ordering": is_ordering,
                "cart_items": cart_items,
                "cart_total": cart_total,
            },
        )


def item_list(request, category_id):
    is_ordering = request.session.get("is_ordering", False)
    category = get_object_or_404(Category, id=category_id)

    if request.user.is_authenticated and category.name == "Uncategorized":
        items = category.items.all().order_by(Lower("name"))
    else:
        items = category.items.filter(is_active=True).order_by(Lower("name"))

    cart = request.session.get("ticket_cart", {})
    cart_items = []
    cart_item_ids = []
    cart_total = Decimal(0)

    if is_ordering:
        for item_id_str, qty in cart.items():
            try:
                cart_item = Item.objects.get(id=int(item_id_str))
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
        },
    )


def item_list_pdf(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    items = category.items.filter(is_active=True).order_by(Lower("name"))
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


# ==========================================
# PHASE 3: THE SYNC PORTAL ENGINE
# ==========================================
@login_required
def sync_inventory(request):
    if not request.user.is_staff:
        return redirect("category_list")

    if request.method == "POST":
        excel_file = request.FILES.get("excel_file")

        if not excel_file:
            messages.error(request, "Please select a file to upload.")
            return redirect("sync_inventory")
        if not excel_file.name.endswith(".xlsx"):
            messages.error(request, "Invalid format. Please upload an .xlsx file.")
            return redirect("sync_inventory")

        current_row_number = 1
        current_processing_barcode = "N/A"

        try:
            uncategorized_folder, created = Category.objects.get_or_create(
                name="Uncategorized"
            )

            wb = openpyxl.load_workbook(excel_file, data_only=True)
            sheet = wb.active

            rows = list(sheet.iter_rows(values_only=True))
            if len(rows) < 2:
                messages.error(request, "The uploaded file is empty or missing data.")
                return redirect("sync_inventory")

            headers = [str(col).upper().strip() if col else "" for col in rows[0]]

            try:
                code_idx = headers.index("CODE")
                item_idx = headers.index("ITEM")
                qtnet_idx = headers.index("QTNET")
                salepr_idx = headers.index("SALEPR")
            except ValueError:
                messages.error(
                    request,
                    "Missing required columns. Ensure CODE, ITEM, QTNET, and SALEPR exist.",
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

                # --- NEW LOGIC: Round the Excel price to 2 decimal places to match database ---
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
                    try:
                        Item.objects.create(
                            name=raw_name,
                            category=uncategorized_folder,
                            barcode=raw_code,
                            stock_quantity=stock,
                            price=price,
                            is_active=False,
                        )
                    except IntegrityError:
                        Item.objects.create(
                            name=f"{raw_name} ({raw_code})",
                            category=uncategorized_folder,
                            barcode=raw_code,
                            stock_quantity=stock,
                            price=price,
                            is_active=False,
                        )

            # Remove items that are no longer in the Excel file
            uncategorized_folder.items.exclude(barcode__in=synced_barcodes).delete()

            uncategorized_count = uncategorized_folder.items.count()

            messages.success(
                request,
                f"🚀 Sync Complete! {items_updated} active items were updated. There are {uncategorized_count} items currently sitting in the 'Uncategorized' folder.",
            )

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
    clients = Client.objects.all().order_by("name")
    return render(request, "catalog/client_list.html", {"clients": clients})


@login_required
def client_detail(request, client_id):
    client = get_object_or_404(Client, id=client_id)

    orders_qs = client.orders.all().order_by("created_at")
    orders = []

    for i, order in enumerate(orders_qs, 1):
        order.client_order_number = i
        orders.append(order)

    orders.reverse()

    return render(
        request, "catalog/client_detail.html", {"client": client, "orders": orders}
    )


@login_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id)
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
        },
    )


@login_required
def order_pdf(request, order_id):
    order = get_object_or_404(Order, id=order_id)
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
        items = Item.objects.filter(
            (Q(name__icontains=query) | Q(description__icontains=query))
            & Q(is_active=True)
        ).order_by(Lower("name"))[:15]

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
