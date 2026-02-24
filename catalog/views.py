from datetime import datetime
from decimal import Decimal  # <--- Needed for the price math
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q
from django.db.models.functions import Lower  # <--- NEW: Smart Sort Tool
from django.contrib.auth.decorators import login_required
from .models import Category, Item
from .forms import ItemForm
from .utils import render_to_pdf

def category_list(request):
    # 1. Check if the user is searching for something
    query = request.GET.get('q')

    if query:
        # SEARCH MODE: Look for items matching the name or description
        # ADDED: .order_by(Lower('name')) to sort search results A-Z (Smart Sort)
        items = Item.objects.filter(
            Q(name__icontains=query) | 
            Q(description__icontains=query)
        ).order_by(Lower('name'))
        
        # Render the Item List page directly with the results
        return render(request, "catalog/item_list.html", {
            "items": items,
            "search_query": query,
            "category": None 
        })
    else:
        # NORMAL MODE: Show the Category Buttons
        categories = Category.objects.all()
        return render(request, "catalog/category_list.html", {"categories": categories})


def item_list(request, category_id):
    # 1. Get the specific category
    category = get_object_or_404(Category, id=category_id)

    # 2. Get items for this category
    # ADDED: .order_by(Lower('name')) so they appear A-Z on the website
    items = category.items.all().order_by(Lower('name'))

    # 3. Render the list
    return render(
        request, "catalog/item_list.html", {"category": category, "items": items}
    )


def item_list_pdf(request, category_id):
    # 1. Get category and items
    category = get_object_or_404(Category, id=category_id)
    
    # 2. Get items sorted A-Z
    # ADDED: .order_by(Lower('name')) to fix the "Mars" separation issue
    items = category.items.all().order_by(Lower('name'))

    # 3. Prepare data
    context = {
        "category": category,
        "items": items,
        "pagesize": "A4",
    }

    # 4. Generate PDF
    pdf = render_to_pdf("catalog/pdf_template.html", context)

    if pdf:
        response = HttpResponse(pdf, content_type="application/pdf")
        
        # Create a nice filename with the date
        current_date = datetime.now().strftime("%Y-%m-%d")
        filename = f"{category.name}_{current_date}.pdf"
        
        # 'attachment' makes it download. 'inline' would open it in the browser.
        content = f"attachment; filename={filename}"
        response["Content-Disposition"] = content
        return response

    return HttpResponse("Not found")


@login_required
def edit_item(request, item_id):
    # 1. Get the item or show 404 error
    item = get_object_or_404(Item, id=item_id)

    if request.method == "POST":
        # 2. If User clicked "Save", update the data
        form = ItemForm(request.POST, request.FILES, instance=item)
        if form.is_valid():
            form.save()
            # Go back to the list so we can see the changes
            if item.category:
                return redirect('item_list', category_id=item.category.id)
            else:
                return redirect('category_list')
    else:
        # 3. If User just opened the page, fill the form with existing data
        form = ItemForm(instance=item)

    return render(request, 'catalog/edit_item.html', {'form': form, 'item': item})


# --- FUNCTION FOR DUPLICATING CATEGORY ---
@login_required
def duplicate_category(request, category_id):
    # 1. Get the original category
    original_category = get_object_or_404(Category, id=category_id)

    if request.method == "POST":
        # 2. Get data from the form
        new_name = request.POST.get('new_name')
        try:
            percentage = Decimal(request.POST.get('percentage', 0))
        except:
            percentage = Decimal(0)

        # 3. Create the New Category
        try:
            new_category = Category.objects.create(name=new_name)
        except:
            return HttpResponse(f"Error: A category named '{new_name}' already exists. Please go back and choose a different name.")

        # 4. Loop through old items and copy them
        # ADDED: .order_by(Lower('name')) so the new items are created in alphabetical order
        old_items = original_category.items.all().order_by(Lower('name'))
        
        for item in old_items:
            # Calculate new price
            factor = 1 + (percentage / 100)
            new_price = item.price * factor
            
            # Create the copy
            Item.objects.create(
                category=new_category,     # Link to NEW category
                name=item.name,            # Same name
                description=item.description, # Same description
                price=new_price,           # NEW PRICE
                image=item.image           # Same image file
            )

        # 5. Done! Go to the new category page
        return redirect('item_list', category_id=new_category.id)

    # If GET request, show the form
    return render(request, 'catalog/duplicate_category.html', {'category': original_category})