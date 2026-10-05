from django.db.models import ObjectDoesNotExist
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render, redirect

from carts.models import Cart, CartItem
from store.models import Product, Variation
from django.contrib.auth.decorators import login_required
from rest_framework.decorators import api_view,permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

TAX_RATE=18

def cart_id(request):
    cart=request.session.session_key
    if not cart:
        cart=request.session.create()
    return cart


def add_cart(request, product_id):
    current_user=request.user
    product=Product.objects.get(id=product_id)

    if current_user.is_authenticated:
        product_variation=[]

        if request.method=='POST':
            for item in request.POST:
                key=item
                value=request.POST[key]

                try:
                    variation=Variation.objects.get(
                        product=product,
                        variation_category__iexact=key,
                        variation_value__iexact=value
                    )
                    product_variation.append(variation)
                except:
                    pass

        is_cart_item_exists=CartItem.objects.filter(
            product=product,
            user=current_user
        ).exists()

        if is_cart_item_exists:
            cart_item=CartItem.objects.filter(
                product=product,
                user=current_user
            )

            ex_var_list=[]
            id=[]

            for item in cart_item:
                existing_variation=item.variations.all()
                ex_var_list.append(list(existing_variation))
                id.append(item.id)

            if product_variation in ex_var_list:
                index=ex_var_list.index(product_variation)
                item_id=id[index]
                item=CartItem.objects.get(
                    product=product,
                    id=item_id
                )
                item.quantity+=1
                item.save()
            else:
                item=CartItem.objects.create(
                    product=product,
                    quantity=1,
                    user=current_user
                )

                if len(product_variation)>0:
                    item.variations.clear()
                    item.variations.add(*product_variation)

                item.save()
        else:
            cart_item=CartItem.objects.create(
                product=product,
                quantity=1,
                user=current_user
            )

            if len(product_variation)>0:
                cart_item.variations.clear()
                cart_item.variations.add(*product_variation)

            cart_item.save()

        return redirect('cart')

    else:
        product_variation=[]

        if request.method=='POST':
            for item in request.POST:
                key=item
                value=request.POST[key]

                try:
                    variation=Variation.objects.get(
                        product=product,
                        variation_category__iexact=key,
                        variation_value__iexact=value
                    )
                    product_variation.append(variation)
                except:
                    pass

        try:
            cart=Cart.objects.get(cart_id=cart_id(request))
        except Cart.DoesNotExist:
            cart=Cart.objects.create(
                cart_id=cart_id(request)
            )

        cart.save()

        is_cart_item_exists=CartItem.objects.filter(
            product=product,
            cart=cart
        ).exists()

        if is_cart_item_exists:
            cart_item=CartItem.objects.filter(
                product=product,
                cart=cart
            )

            ex_var_list=[]
            id=[]

            for item in cart_item:
                existing_variation=item.variations.all()
                ex_var_list.append(list(existing_variation))
                id.append(item.id)

            if product_variation in ex_var_list:
                index=ex_var_list.index(product_variation)
                item_id=id[index]

                item=CartItem.objects.get(
                    product=product,
                    id=item_id
                )

                item.quantity+=1
                item.save()
            else:
                item=CartItem.objects.create(
                    product=product,
                    quantity=1,
                    cart=cart
                )

                if len(product_variation)>0:
                    item.variations.clear()
                    item.variations.add(*product_variation)

                item.save()
        else:
            cart_item=CartItem.objects.create(
                product=product,
                quantity=1,
                cart=cart
            )

            if len(product_variation)>0:
                cart_item.variations.clear()
                cart_item.variations.add(*product_variation)

            cart_item.save()

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


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_add_to_cart(request):

    product_id = request.data.get('product_id')
    quantity = request.data.get('quantity', 1)
    variation_ids = request.data.get('variation_ids', [])

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
    except Product.DoesNotExist:
        return Response(
            {'message': 'Product not found or unavailable.'},
            status=status.HTTP_404_NOT_FOUND
        )

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

    if quantity > product.stock:
        return Response(
            {'message': f'Only {product.stock} items are available.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Get selected variations
    variations = Variation.objects.none()

    if variation_ids:

        if not isinstance(variation_ids, list):
            return Response(
                {'message': 'variation_ids must be a list.'},
                status=status.HTTP_400_BAD_REQUEST
            )

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

    # Find cart items for same product
    cart_items = CartItem.objects.filter(
        user=request.user,
        product=product,
        is_active=True
    )

    existing_cart_item = None

    # Compare variations
    selected_variation_ids = set(
        variations.values_list('id', flat=True)
    )

    for item in cart_items:

        existing_variation_ids = set(
            item.variations.values_list('id', flat=True)
        )

        if existing_variation_ids == selected_variation_ids:
            existing_cart_item = item
            break

    if existing_cart_item:

        new_quantity = existing_cart_item.quantity + quantity

        if new_quantity > product.stock:
            return Response(
                {
                    'message': f'Only {product.stock} items are available.'
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