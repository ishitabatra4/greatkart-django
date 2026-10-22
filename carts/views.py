from django.db.models import ObjectDoesNotExist
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render, redirect

from carts.models import Cart, CartItem
from store.models import Product, Variation
from django.contrib.auth.decorators import login_required
from rest_framework.decorators import api_view,permission_classes
from rest_framework.permissions import IsAuthenticated,IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from django.contrib import messages

TAX_RATE=18

def cart_id(request):
    cart=request.session.session_key
    if not cart:
        cart=request.session.create()
    return cart

def add_cart(request, product_id):
    if request.method != 'POST':
        return redirect(
            request.META.get('HTTP_REFERER', 'store')
        )

    current_user = request.user
    product = Product.objects.get(id=product_id)

    # 1. Validate required size/color BEFORE adding to cart
    is_valid, error_message = validate_product_variations(
        request, product
    )

    if not is_valid:
        messages.error(request, error_message)
        return redirect(
            request.META.get('HTTP_REFERER', 'store')
        )

    # 2. Check product availability
    if not product.is_available or product.stock <= 0:
        messages.error(
            request,
            'This product is currently out of stock.'
        )
        return redirect(
            request.META.get('HTTP_REFERER', 'store')
        )

    # 3. Get selected variations
    product_variation = []

    for key in ['color', 'size']:
        value = request.POST.get(key, '').strip()

        if value:
            variation = Variation.objects.filter(
                product=product,
                variation_category__iexact=key,
                variation_value__iexact=value,
                is_active=True
            ).first()

            if variation:
                product_variation.append(variation)

    # 4. Authenticated user cart
    if current_user.is_authenticated:
        cart_items = CartItem.objects.filter(
            product=product,
            user=current_user
        )

        existing_item = None

        for item in cart_items:
            existing_variations = list(item.variations.all())

            if (
                len(existing_variations) == len(product_variation)
                and set(existing_variations) == set(product_variation)
            ):
                existing_item = item
                break

        if existing_item:
            if existing_item.quantity + 1 > product.stock:
                messages.error(
                    request,
                    f'Only {product.stock} item(s) of '
                    f'{product.product_name} are available.'
                )
                return redirect(
                    request.META.get('HTTP_REFERER', 'store')
                )

            existing_item.quantity += 1
            existing_item.save()

        else:
            cart_item = CartItem.objects.create(
                product=product,
                user=current_user,
                quantity=1
            )

            if product_variation:
                cart_item.variations.add(*product_variation)

        return redirect('cart')

    # 5. Guest user cart
    cart, created = Cart.objects.get_or_create(
        cart_id=cart_id(request)
    )

    cart_items = CartItem.objects.filter(
        product=product,
        cart=cart
    )

    existing_item = None

    for item in cart_items:
        existing_variations = list(item.variations.all())

        if (
            len(existing_variations) == len(product_variation)
            and set(existing_variations) == set(product_variation)
        ):
            existing_item = item
            break

    if existing_item:
        if existing_item.quantity + 1 > product.stock:
            messages.error(
                request,
                f'Only {product.stock} item(s) of '
                f'{product.product_name} are available.'
            )
            return redirect(
                request.META.get('HTTP_REFERER', 'store')
            )

        existing_item.quantity += 1
        existing_item.save()

    else:
        cart_item = CartItem.objects.create(
            product=product,
            cart=cart,
            quantity=1
        )

        if product_variation:
            cart_item.variations.add(*product_variation)

    return redirect('cart')

def remove_cart(request, product_id, cart_item_id):
    product=get_object_or_404(Product, id=product_id)

    try:
        if request.user.is_authenticated:
            cart_item=CartItem.objects.get(
                product=product,
                user=request.user,
                id=cart_item_id
            )
        else:
            cart=Cart.objects.get(cart_id=cart_id(request))
            cart_item=CartItem.objects.get(
                product=product,
                cart=cart,
                id=cart_item_id
            )

        if cart_item.quantity>1:
            cart_item.quantity-=1
            cart_item.save()
        else:
            cart_item.delete()

    except CartItem.DoesNotExist:
        pass

    return redirect('cart')


def remove_cart_item(request, product_id, cart_item_id):
    product=get_object_or_404(Product, id=product_id)

    if request.user.is_authenticated:
        cart_item=CartItem.objects.get(
            product=product,
            user=request.user,
            id=cart_item_id
        )
    else:
        cart=Cart.objects.get(cart_id=cart_id(request))
        cart_item=CartItem.objects.get(
            product=product,
            cart=cart,
            id=cart_item_id
        )

    cart_item.delete()

    return redirect('cart')


def cart(request, total=0, quantity=0, cart_items=None):
    try:
        tax=0
        grand_total=0

        if request.user.is_authenticated:
            cart_items=CartItem.objects.filter(
                user=request.user
            )
        else:
            cart=Cart.objects.get(
                cart_id=cart_id(request)
            )

            cart_items=CartItem.objects.filter(
                cart=cart
            )

        for cart_item in cart_items:
            total+=cart_item.product.price*cart_item.quantity
            quantity+=cart_item.quantity

        tax=(total*TAX_RATE)/100
        grand_total=total+tax

    except ObjectDoesNotExist:
        pass

    context={
        'total':total,
        'quantity':quantity,
        'cart_items':cart_items,
        'tax':tax,
        'grand_total':grand_total
    }

    return render(request,'store/cart.html',context)


@login_required(login_url='login')
def checkout(request, total=0, quantity=0, cart_items=None):
    try:
        tax=0
        grand_total=0

        if request.user.is_authenticated:
            cart_items=CartItem.objects.filter(
                user=request.user
            )
        else:
            cart=Cart.objects.get(
                cart_id=cart_id(request)
            )

            cart_items=CartItem.objects.filter(
                cart=cart
            )

        for cart_item in cart_items:
            total+=cart_item.product.price*cart_item.quantity
            quantity+=cart_item.quantity

        tax=(total*TAX_RATE)/100
        grand_total=total+tax

    except ObjectDoesNotExist:
        pass

    context={
        'total':total,
        'quantity':quantity,
        'cart_items':cart_items,
        'tax':tax,
        'grand_total':grand_total
    }

    return render(request,'store/checkout.html',context)

def validate_product_variations(request, product):
    """
    If a product has active size/color options, require a valid
    selection for each available category.
    """
    required_categories = list(
        Variation.objects.filter(
            product=product,
            is_active=True,
            variation_category__in=["color", "size"],
        )
        .values_list("variation_category", flat=True)
        .distinct()
    )

    for category in required_categories:
        selected_value = request.POST.get(category, "").strip()

        if not selected_value:
            return False, f"Please select a {category}."

        exists = Variation.objects.filter(
            product=product,
            is_active=True,
            variation_category=category,
            variation_value__iexact=selected_value,
        ).exists()

        if not exists:
            return False, f"Please select a valid {category}."

    return True, ""



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_add_to_cart(request):

    product_id = request.data.get('product_id')
    quantity = request.data.get('quantity', 1)
    variation_ids = request.data.get('variation_ids', [])

    # 1. Validate product ID
    if not product_id:
        return Response(
            {'message': 'product_id is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        product = Product.objects.get(
            id=product_id,
            is_available=True
        )
    except (Product.DoesNotExist, ValueError, TypeError):
        return Response(
            {'message': 'Product not found or unavailable.'},
            status=status.HTTP_404_NOT_FOUND
        )

    # 2. Validate quantity
    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        return Response(
            {'message': 'Quantity must be a valid number.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if quantity < 1:
        return Response(
            {'message': 'Quantity must be at least 1.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if product.stock <= 0:
        return Response(
            {'message': 'This product is currently out of stock.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if quantity > product.stock:
        return Response(
            {'message': f'Only {product.stock} items are available.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # 3. Validate variation_ids format
    if not isinstance(variation_ids, list):
        return Response(
            {'message': 'variation_ids must be a list.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        variation_ids = [int(v) for v in variation_ids]
    except (TypeError, ValueError):
        return Response(
            {'message': 'Invalid variation IDs.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if len(variation_ids) != len(set(variation_ids)):
        return Response(
            {'message': 'Duplicate variations are not allowed.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # 4. Fetch valid variations belonging to this product
    variations = Variation.objects.filter(
        id__in=variation_ids,
        product=product,
        is_active=True
    )

    if variations.count() != len(variation_ids):
        return Response(
            {'message': 'Invalid variation selected.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # 5. Identify available size/color categories
    required_categories = set(
        Variation.objects.filter(
            product=product,
            is_active=True,
            variation_category__in=['color', 'size']
        ).values_list(
            'variation_category', flat=True
        )
    )

    selected_categories_list = list(
        variations.values_list(
            'variation_category', flat=True
        )
    )

    # Normalize category names for comparisons
    required_categories = {
        category.lower() for category in required_categories
    }
    selected_categories_list = [
        category.lower() for category in selected_categories_list
    ]

    # Only one value per category is allowed
    if len(selected_categories_list) != len(
        set(selected_categories_list)
    ):
        return Response(
            {
                'message':
                    'Select only one value for each option.'
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    selected_categories = set(selected_categories_list)

    # Require every available size/color category
    if not required_categories.issubset(selected_categories):
        missing = required_categories - selected_categories

        return Response(
            {
                'message': (
                    'Please select: '
                    + ', '.join(sorted(missing))
                    + '.'
                )
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    # 6. Find existing cart item with exactly the same variations
    cart_items = CartItem.objects.filter(
        user=request.user,
        product=product,
        is_active=True
    )

    selected_variation_ids = set(variation_ids)
    existing_cart_item = None

    for item in cart_items:
        existing_variation_ids = set(
            item.variations.values_list('id', flat=True)
        )

        if existing_variation_ids == selected_variation_ids:
            existing_cart_item = item
            break

    # 7. Update existing item or create a new one
    if existing_cart_item:

        new_quantity = existing_cart_item.quantity + quantity

        if new_quantity > product.stock:
            return Response(
                {
                    'message': (
                        f'Only {product.stock} items are available.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        existing_cart_item.quantity = new_quantity
        existing_cart_item.save()
        cart_item = existing_cart_item

    else:

        cart = Cart.objects.filter(
            cart_id=f'user-{request.user.id}'
        ).first()

        if not cart:
            cart = Cart.objects.create(
                cart_id=f'user-{request.user.id}'
            )

        cart_item = CartItem.objects.create(
            user=request.user,
            product=product,
            cart=cart,
            quantity=quantity
        )

        cart_item.variations.set(variations)

    # 8. Return response
    return Response(
        {
            'message': 'Product added to cart successfully.',
            'cart_item_id': cart_item.id,
            'product_id': product.id,
            'product_name': product.product_name,
            'quantity': cart_item.quantity,
            'price': float(product.price),
            'sub_total': float(cart_item.sub_total()),
            'variations': [
                {
                    'id': variation.id,
                    'category': variation.variation_category,
                    'value': variation.variation_value
                }
                for variation in cart_item.variations.all()
            ]
        },
        status=status.HTTP_201_CREATED
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_view_cart(request):

    cart_items=CartItem.objects.filter(
        user=request.user,
        is_active=True
    ).select_related('product')

    items=[]
    total=0

    for item in cart_items:

        sub_total=item.sub_total()
        total+=sub_total

        items.append({
            'cart_item_id':item.id,
            'product_id':item.product.id,
            'product_name':item.product.product_name,
            'price':item.product.price,
            'quantity':item.quantity,
            'sub_total':sub_total,
        })

    return Response({
        'items':items,
        'total':total
    })

@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def api_update_cart_item(request, cart_item_id):

    try:
        cart_item = CartItem.objects.get(
            id=cart_item_id,
            user=request.user,
            is_active=True
        )
    except CartItem.DoesNotExist:
        return Response(
            {
                'message': 'Cart item not found.'
            },
            status=status.HTTP_404_NOT_FOUND
        )

    action = request.data.get('action')

    if action not in ['increase', 'decrease']:
        return Response(
            {
                'message': 'action must be increase or decrease.'
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    if action == 'increase':

        if cart_item.quantity >= cart_item.product.stock:
            return Response(
                {
                    'message': f'Only {cart_item.product.stock} items are available.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        cart_item.quantity += 1

    elif action == 'decrease':

        if cart_item.quantity <= 1:
            return Response(
                {
                    'message': 'Quantity cannot be less than 1.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        cart_item.quantity -= 1

    cart_item.save()

    return Response(
        {
            'message': 'Cart quantity updated successfully.',
            'cart_item_id': cart_item.id,
            'product_id': cart_item.product.id,
            'quantity': cart_item.quantity,
            'price': float(cart_item.product.price),
            'subtotal': float(cart_item.sub_total()),
        },
        status=status.HTTP_200_OK
    )

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def api_remove_cart_item(request,cart_item_id):

    try:
        cart_item=CartItem.objects.get(
            id=cart_item_id,
            user=request.user,
            is_active=True
        )
    except CartItem.DoesNotExist:
        return Response(
            {
                'message':'Cart item not found.'
            },
            status=status.HTTP_404_NOT_FOUND
        )

    cart_item.delete()

    return Response(
        {
            'message':'Cart item removed successfully.'
        },
        status=status.HTTP_200_OK
    )

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def api_clear_cart(request):

    cart_items = CartItem.objects.filter(
        user=request.user,
        is_active=True
    )

    deleted_count = cart_items.count()

    cart_items.delete()

    return Response(
        {
            'message': 'Cart cleared successfully.',
            'deleted_items': deleted_count
        },
        status=status.HTTP_200_OK
    )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_cart(request):

    cart_items = CartItem.objects.filter(
        user=request.user,
        is_active=True
    ).select_related('product').prefetch_related('variations')

    items = []
    subtotal = 0
    quantity = 0

    for item in cart_items:

        item_subtotal = item.product.price * item.quantity

        variations = []

        for variation in item.variations.all():
            variations.append({
                'id': variation.id,
                'category': variation.variation_category,
                'value': variation.variation_value
            })

        items.append({
            'cart_item_id': item.id,
            'product_id': item.product.id,
            'product_name': item.product.product_name,
            'price': float(item.product.price),
            'quantity': item.quantity,
            'subtotal': float(item_subtotal),
            'stock': item.product.stock,
            'variations': variations,
            'image': request.build_absolute_uri(
                item.product.images.url
            ) if item.product.images else None
        })

        subtotal += item_subtotal
        quantity += item.quantity

    tax = (subtotal * 18) / 100
    grand_total = subtotal + tax

    return Response({
        'count': len(items),
        'quantity': quantity,
        'items': items,
        'summary': {
            'subtotal': round(subtotal, 2),
            'tax_rate': 18,
            'tax': round(tax, 2),
            'grand_total': round(grand_total, 2)
        }
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_checkout(request):

    cart_items = CartItem.objects.filter(
        user=request.user,
        is_active=True
    ).select_related('product').prefetch_related('variations')

    if not cart_items.exists():
        return Response(
            {
                'message': 'Your cart is empty.'
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    subtotal = 0
    quantity = 0
    items = []

    for cart_item in cart_items:

        item_subtotal = (
            cart_item.product.price *
            cart_item.quantity
        )

        subtotal += item_subtotal
        quantity += cart_item.quantity

        items.append(
            {
                'cart_item_id': cart_item.id,
                'product_id': cart_item.product.id,
                'product_name': cart_item.product.product_name,
                'price': float(cart_item.product.price),
                'quantity': cart_item.quantity,
                'subtotal': float(item_subtotal),
                'stock': cart_item.product.stock,
                'variations': [
                    {
                        'id': variation.id,
                        'category': variation.variation_category,
                        'value': variation.variation_value
                    }
                    for variation in cart_item.variations.all()
                ]
            }
        )

    tax = (subtotal * TAX_RATE) / 100
    grand_total = subtotal + tax

    return Response(
        {
            'items': items,
            'summary': {
                'quantity': quantity,
                'subtotal': float(subtotal),
                'tax_rate': TAX_RATE,
                'tax': float(tax),
                'grand_total': float(grand_total)
            }
        },
        status=status.HTTP_200_OK
    )

@api_view(['GET'])
@permission_classes([IsAdminUser])
def api_admin_carts(request):

    cart_items = CartItem.objects.filter(
        is_active=True
    ).select_related(
        'user',
        'product',
        'cart'
    ).prefetch_related(
        'variations'
    ).order_by('-cart__date_added')

    carts_data = {}

    for item in cart_items:

        cart_id = item.cart.id if item.cart else None

        if cart_id not in carts_data:

            carts_data[cart_id] = {
                'cart_id': cart_id,
                'cart_key': item.cart.cart_id if item.cart else None,
                'date_added': item.cart.date_added if item.cart else None,

                'customer': {
                    'id': item.user.id if item.user else None,
                    'first_name': item.user.first_name if item.user else None,
                    'last_name': item.user.last_name if item.user else None,
                    'username': item.user.username if item.user else None,
                    'email': item.user.email if item.user else None,
                },

                'items': [],
                'subtotal': 0,
                'quantity': 0
            }

        item_subtotal = item.product.price * item.quantity

        variations = []

        for variation in item.variations.all():

            variations.append({
                'id': variation.id,
                'category': variation.variation_category,
                'value': variation.variation_value
            })

        carts_data[cart_id]['items'].append({

            'cart_item_id': item.id,

            'product': {
                'id': item.product.id,
                'name': item.product.product_name,
                'price': float(item.product.price),
                'stock': item.product.stock
            },

            'quantity': item.quantity,

            'subtotal': float(item_subtotal),

            'variations': variations,

            'is_active': item.is_active
        })

        carts_data[cart_id]['subtotal'] += item_subtotal
        carts_data[cart_id]['quantity'] += item.quantity

    carts = list(carts_data.values())

    # Add tax and grand total
    for cart in carts:

        tax = (cart['subtotal'] * TAX_RATE) / 100
        grand_total = cart['subtotal'] + tax

        cart['subtotal'] = round(cart['subtotal'], 2)

        cart['tax'] = round(tax, 2)

        cart['grand_total'] = round(grand_total, 2)

    return Response({
        'count': len(carts),
        'carts': carts
    })

@api_view(['DELETE'])
@permission_classes([IsAdminUser])
def api_admin_cart_delete(request, cart_id):

    try:
        cart = Cart.objects.get(id=cart_id)

    except Cart.DoesNotExist:

        return Response(
            {
                'message': 'Cart not found.'
            },
            status=status.HTTP_404_NOT_FOUND
        )

    cart_items_count = CartItem.objects.filter(
        cart=cart
    ).count()

    cart_key = cart.cart_id

    cart.delete()

    return Response({
        'message': 'Cart deleted successfully.',
        'cart_id': cart_id,
        'cart_key': cart_key,
        'deleted_items': cart_items_count
    })

@api_view(['GET'])
@permission_classes([IsAdminUser])
def api_admin_cart_detail(request, cart_id):

    try:
        cart = Cart.objects.get(id=cart_id)
    except Cart.DoesNotExist:
        return Response(
            {'message': 'Cart not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    cart_items = CartItem.objects.filter(
        cart=cart,
        is_active=True
    ).select_related('product').prefetch_related('variations')

    items = []

    subtotal = 0
    total_quantity = 0

    for item in cart_items:

        item_subtotal = item.product.price * item.quantity

        variations = []

        for variation in item.variations.all():
            variations.append({
                'id': variation.id,
                'category': variation.variation_category,
                'value': variation.variation_value
            })

        items.append({
            'cart_item_id': item.id,
            'product': {
                'id': item.product.id,
                'name': item.product.product_name,
                'price': item.product.price,
                'stock': item.product.stock
            },
            'quantity': item.quantity,
            'subtotal': item_subtotal,
            'variations': variations,
            'is_active': item.is_active
        })

        subtotal += item_subtotal
        total_quantity += item.quantity

    tax = (18 * subtotal) / 100
    grand_total = subtotal + tax

    return Response({
        'cart_id': cart.id,
        'cart_key': cart.cart_id,
        'date_added': cart.date_added,

        'customer': {
            'id': cart_items.first().user.id if cart_items and cart_items.first().user else None,
            'first_name': cart_items.first().user.first_name if cart_items and cart_items.first().user else None,
            'last_name': cart_items.first().user.last_name if cart_items and cart_items.first().user else None,
            'username': cart_items.first().user.username if cart_items and cart_items.first().user else None,
            'email': cart_items.first().user.email if cart_items and cart_items.first().user else None
        },

        'items': items,
        'subtotal': subtotal,
        'quantity': total_quantity,
        'tax': tax,
        'grand_total': grand_total
    })