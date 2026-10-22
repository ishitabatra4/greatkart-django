from django.shortcuts import render,redirect
from django.contrib import messages
from django.db import transaction
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings
from carts.models import CartItem
from .forms import OrderForm
from .models import Order,Payment,OrderProduct
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated,IsAdminUser
from rest_framework.response import Response
from rest_framework import status

from orders.models import Order, OrderProduct,Payment
from store.models import Product
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required
from accounts.models import UserProfile
from django.shortcuts import get_object_or_404
import datetime
import datetime
import uuid
TAX_RATE=18
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages

from .models import Order
from carts.models import CartItem
from .invoice_utils import generate_vendor_invoices

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import Order


@login_required
def payments(request):
    order_number = request.GET.get("order_number")

    if not order_number:
        order_number = request.session.get("greatkart_order_number")

    if not order_number:
        messages.error(request, "Order number missing hai.")
        return redirect("checkout")

    order = Order.objects.filter(
        order_number=order_number,
        user=request.user,
        is_ordered=False,
    ).first()

    if not order:
        messages.error(request, "Pending order nahi mila.")
        return redirect("checkout")

    cart_items = CartItem.objects.filter(
        user=request.user
    ).select_related("product").prefetch_related("variations")

    grand_total = Decimal(str(order.order_total or 0))
    tax = Decimal(str(order.tax or 0))
    total = grand_total - tax

    context = {
        "order": order,
        "cart_items": cart_items,
        "total": total,
        "tax": tax,
        "grand_total": grand_total,
    }

    return render(request, "orders/payments.html", context)



def place_order(request,total=0,quantity=0):
    current_user=request.user
    cart_items=CartItem.objects.filter(user=current_user)
    cart_count=cart_items.count()

    if cart_count<=0:
        return redirect('store')

    grand_total=0
    tax=0

    for cart_item in cart_items:
        total+=cart_item.product.price*cart_item.quantity
        quantity+=cart_item.quantity

    tax=(total*TAX_RATE)/100
    grand_total=total+tax

    if request.method=='POST':
        form=OrderForm(request.POST)

        if form.is_valid():
            data=Order()
            data.user=current_user
            data.first_name=form.cleaned_data['first_name']
            data.last_name=form.cleaned_data['last_name']
            data.phone=form.cleaned_data['phone']
            data.email=form.cleaned_data['email']
            data.address_line_1=form.cleaned_data['address_line_1']
            data.address_line_2=form.cleaned_data['address_line_2']
            data.country=form.cleaned_data['country']
            data.state=form.cleaned_data['state']
            data.city=form.cleaned_data['city']
            data.order_note=form.cleaned_data['order_note']
            data.order_total=grand_total
            data.tax=tax
            data.ip=request.META.get('REMOTE_ADDR')
            data.save()

            yr=int(datetime.date.today().strftime('%Y'))
            mt=int(datetime.date.today().strftime('%m'))
            dt=int(datetime.date.today().strftime('%d'))
            current_date=datetime.date(yr,mt,dt).strftime('%Y%m%d')
            order_number=current_date+str(data.id)

            data.order_number=order_number
            data.save()

            order=Order.objects.get(
                user=current_user,
                is_ordered=False,
                order_number=order_number
            )

            context={
                'order':order,
                'cart_items':cart_items,
                'total':total,
                'tax':tax,
                'grand_total':grand_total,
            }

            return render(request,'orders/payments.html',context)

    return redirect('checkout')


def confirm_payment(request):
    if request.method!='POST':
        return redirect('checkout')

    current_user=request.user
    order_number=request.POST.get('order_number')
    payment_method=request.POST.get('payment_method')

    try:
        order=Order.objects.get(
            order_number=order_number,
            user=current_user,
            is_ordered=False
        )
    except Order.DoesNotExist:
        messages.error(request,'Invalid or already processed order.')
        return redirect('store')

    if not payment_method:
        messages.error(request,'Please select a payment method.')
        return redirect('checkout')

    if order.payment:
        messages.error(request,'Payment has already been made for this order.')
        return redirect('store')

    cart_items=CartItem.objects.filter(user=current_user)

    if not cart_items.exists():
        messages.error(request,'Your cart is empty.')
        return redirect('store')

    with transaction.atomic():
        payment_id='PAY-'+uuid.uuid4().hex[:12].upper()

        for cart_item in cart_items:
            product=cart_item.product.__class__.objects.select_for_update().get(
                id=cart_item.product.id
            )

            if product.stock<cart_item.quantity:
                messages.error(
                    request,
                    f'Sorry, only {product.stock} item(s) of {product.product_name} are available.'
                )
                return redirect('checkout')

        payment=Payment.objects.create(
            user=current_user,
            payment_id=payment_id,
            payment_method=payment_method,
            amount_paid=str(order.order_total),
            status='Completed'
        )

        order.payment=payment
        order.is_ordered=True
        order.status='New'
        order.save()

        for cart_item in cart_items:
            product=cart_item.product.__class__.objects.select_for_update().get(
                id=cart_item.product.id
            )

            order_product=OrderProduct()
            order_product.order=order
            order_product.payment=payment
            order_product.user=current_user
            order_product.product=product
            order_product.quantity=cart_item.quantity
            order_product.product_price=product.price
            order_product.ordered=True

            color=''
            size=''
            variations=list(cart_item.variations.all())

            for item in variations:
                if item.variation_category.lower()=='color':
                    color=item.variation_value
                elif item.variation_category.lower()=='size':
                    size=item.variation_value

            order_product.color=color
            order_product.size=size
            order_product.save()
            order_product.variations.set(variations)

            product.stock-=cart_item.quantity

            if product.stock==0:
                product.is_available=False

            product.save()
        generate_vendor_invoices(order)    

        cart_items.delete()

        email_subject='Order Received - '+order.order_number

        email_message=render_to_string(
            'orders/order_received_email.html',
            {
                'user':current_user,
                'order':order,
                'payment':payment,
            }
        )

        email=EmailMessage(
            email_subject,
            email_message,
            settings.DEFAULT_FROM_EMAIL,
            [order.email]
        )

        transaction.on_commit(lambda: email.send(fail_silently=True))

    return redirect('order_complete',order_number=order.order_number)


@login_required
def order_complete(request, order_number):
    try:
        order = Order.objects.get(
            order_number=order_number,
            user=request.user,
            is_ordered=True
        )
    except Order.DoesNotExist:
        return redirect('store')

    payment = order.payment

    ordered_products = OrderProduct.objects.filter(
        order=order,
        user=request.user
    ).select_related('product')

    subtotal = sum(
        item.product_price * item.quantity
        for item in ordered_products
    )

    context = {
        'order': order,
        'payment': payment,
        'ordered_products': ordered_products,
        'subtotal': subtotal,
    }

    return render(
        request,
        'orders/order_complete.html',
        context
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def api_payments(request):
    order_number = request.query_params.get("order_number")

    if not order_number:
        return Response(
            {"message": "order_number required hai."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    order = Order.objects.filter(
        order_number=order_number,
        user=request.user,
        is_ordered=False,
    ).first()

    if not order:
        return Response(
            {"message": "Pending order nahi mila."},
            status=status.HTTP_404_NOT_FOUND,
        )

    grand_total = float(order.order_total or 0)
    tax = float(order.tax or 0)

    return Response({
        "order": {
            "order_number": order.order_number,
            "first_name": order.first_name,
            "last_name": order.last_name,
            "full_name": order.full_name(),
            "full_address": order.full_address(),
            "city": order.city,
            "state": order.state,
            "country": order.country,
            "email": order.email,
            "phone": order.phone,
            "order_note": order.order_note,
            "subtotal": round(grand_total - tax, 2),
            "tax": round(tax, 2),
            "grand_total": round(grand_total, 2),
        },
        "payment_methods": [
            {"value": "Dummy Bank Account", "label": "Dummy Bank Account"},
            {"value": "Dummy UPI", "label": "Dummy UPI"},
            {"value": "Dummy Card", "label": "Dummy Card"},
        ],
    })



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_place_order(request):

    current_user = request.user

    # 1. Validate required checkout fields
    required_fields = [
        'first_name',
        'last_name',
        'phone',
        'email',
        'address_line_1',
        'country',
        'state',
        'city'
    ]

    for field in required_fields:
        if not request.data.get(field):
            return Response(
                {'message': f'{field} is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

    # 2. Validate PIN code
    pincode = str(request.data.get('pincode') or '').strip()

    if pincode and (
        len(pincode) != 6 or not pincode.isdigit()
    ):
        return Response(
            {'message': 'Please enter a valid 6-digit PIN code.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # 3. Validate cart, create order and save address atomically
    with transaction.atomic():

        cart_items = list(
            CartItem.objects.filter(
                user=current_user
            ).select_related(
                'product'
            ).prefetch_related(
                'variations'
            ).order_by('product_id', 'id')
        )

        if not cart_items:
            return Response(
                {'message': 'Your cart is empty.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Lock products in a consistent order.
        product_ids = sorted({
            item.product_id for item in cart_items
        })

        locked_products = {
            product.id: product
            for product in Product.objects.select_for_update().filter(
                id__in=product_ids
            ).order_by('id')
        }

        # Aggregate quantities across cart rows.
        requested_quantities = {}

        for cart_item in cart_items:
            requested_quantities[cart_item.product_id] = (
                requested_quantities.get(cart_item.product_id, 0)
                + cart_item.quantity
            )

        # Check product availability and stock.
        for product_id, requested_quantity in requested_quantities.items():
            product = locked_products.get(product_id)

            if product is None or not product.is_available:
                product_name = (
                    product.product_name
                    if product else 'A product in your cart'
                )

                return Response(
                    {
                        'message': (
                            f'{product_name} is no longer available.'
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            if requested_quantity < 1:
                return Response(
                    {
                        'message': (
                            f'Invalid quantity for '
                            f'{product.product_name}.'
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            if product.stock < requested_quantity:
                return Response(
                    {
                        'message': (
                            f'Only {product.stock} item(s) of '
                            f'{product.product_name} are available. '
                            'Please update your cart.'
                        ),
                        'product_id': product.id,
                        'available_stock': product.stock,
                        'requested_quantity': requested_quantity
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

        # 4. Calculate subtotal and quantity.
        total = 0
        quantity = 0

        for cart_item in cart_items:
            product = locked_products[cart_item.product_id]
            total += product.price * cart_item.quantity
            quantity += cart_item.quantity

        tax = (total * TAX_RATE) / 100
        grand_total = total + tax

        # 5. Create pending order.
        data = Order()

        data.user = current_user
        data.first_name = request.data.get('first_name', '').strip()
        data.last_name = request.data.get('last_name', '').strip()
        data.phone = request.data.get('phone', '').strip()
        data.email = request.data.get('email', '').strip()
        data.address_line_1 = request.data.get(
            'address_line_1', ''
        ).strip()
        data.address_line_2 = request.data.get(
            'address_line_2', ''
        ).strip()
        data.country = request.data.get('country', '').strip()
        data.state = request.data.get('state', '').strip()
        data.city = request.data.get('city', '').strip()
        data.pincode = pincode
        data.order_note = request.data.get('order_note', '').strip()

        data.order_total = grand_total
        data.tax = tax
        data.ip = request.META.get('REMOTE_ADDR')

        # Payment has not yet been confirmed.
        data.is_ordered = False
        data.status = 'New'

        data.save()

        # 6. Generate order number.
        current_date = datetime.date.today().strftime('%Y%m%d')
        data.order_number = current_date + str(data.id)

        data.save(update_fields=['order_number'])

        # 7. Save checkout address to customer profile.
        # This makes it available on the next checkout.
        user_profile, _ = UserProfile.objects.get_or_create(
            user=current_user
        )

        user_profile.address_line_1 = data.address_line_1
        user_profile.address_line_2 = data.address_line_2
        user_profile.city = data.city
        user_profile.state = data.state
        user_profile.country = data.country
        user_profile.pincode = data.pincode

        user_profile.save(update_fields=[
            'address_line_1',
            'address_line_2',
            'city',
            'state',
            'country',
            'pincode'
        ])

        # 8. Prepare cart items for the response.
        items = []

        for cart_item in cart_items:
            product = locked_products[cart_item.product_id]
            variations = list(cart_item.variations.all())

            color = ''
            size = ''

            for variation in variations:
                category = variation.variation_category.lower()

                if category == 'color':
                    color = variation.variation_value
                elif category == 'size':
                    size = variation.variation_value

            item_subtotal = product.price * cart_item.quantity

            items.append({
                'cart_item_id': cart_item.id,
                'product_id': product.id,
                'product_name': product.product_name,
                'price': float(product.price),
                'quantity': cart_item.quantity,
                'subtotal': float(item_subtotal),
                'color': color,
                'size': size,
                'variations': [
                    {
                        'id': variation.id,
                        'category': variation.variation_category,
                        'value': variation.variation_value
                    }
                    for variation in variations
                ]
            })

    # 9. Return order details.
    return Response(
        {
            'message': 'Order created successfully.',
            'order': {
                'order_number': data.order_number,
                'first_name': data.first_name,
                'last_name': data.last_name,
                'phone': data.phone,
                'email': data.email,
                'address_line_1': data.address_line_1,
                'address_line_2': data.address_line_2,
                'country': data.country,
                'state': data.state,
                'city': data.city,
                'pincode': data.pincode,
                'order_note': data.order_note,
                'subtotal': float(total),
                'tax_rate': TAX_RATE,
                'tax': float(tax),
                'order_total': float(grand_total),
                'quantity': quantity,
                'status': data.status,
                'is_ordered': data.is_ordered,
                'items': items
            }
        },
        status=status.HTTP_201_CREATED
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_confirm_payment(request):
    current_user = request.user

    order_number = request.data.get('order_number')
    payment_method = request.data.get('payment_method')

    if not order_number:
        return Response(
            {'message': 'order_number is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if not payment_method or not payment_method.strip():
        return Response(
            {'message': 'Please select a payment method.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    payment_method = payment_method.strip()

    allowed_methods = {
        'Dummy Bank Account',
        'Dummy UPI',
        'Dummy Card',
    }

    if payment_method not in allowed_methods:
        return Response(
            {'message': 'Invalid payment method.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    with transaction.atomic():
        try:
            order = Order.objects.select_for_update().get(
                order_number=order_number,
                user=current_user,
                is_ordered=False
            )
        except Order.DoesNotExist:
            return Response(
                {'message': 'Invalid or already processed order.'},
                status=status.HTTP_404_NOT_FOUND
            )

        if order.payment_id:
            return Response(
                {'message': 'Payment already exists for this order.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        cart_items = list(
            CartItem.objects.filter(user=current_user)
            .select_related('product')
            .prefetch_related('variations')
            .order_by('product_id', 'id')
        )

        if not cart_items:
            return Response(
                {'message': 'Your cart is empty.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Aggregate quantities to validate combined stock requirements.
        quantities = {}

        for item in cart_items:
            if item.quantity < 1:
                return Response(
                    {'message': 'Invalid cart quantity.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            quantities[item.product_id] = (
                quantities.get(item.product_id, 0) + item.quantity
            )

        locked_products = {
            product.id: product
            for product in Product.objects.select_for_update()
            .filter(id__in=sorted(quantities.keys()))
            .order_by('id')
        }

        for product_id, requested_quantity in quantities.items():
            product = locked_products.get(product_id)

            if (
                product is None
                or not product.is_available
                or product.stock < requested_quantity
            ):
                available_stock = product.stock if product else 0
                product_name = (
                    product.product_name
                    if product
                    else 'A cart product'
                )

                return Response(
                    {
                        'message': (
                            f'Sorry, only {available_stock} item(s) '
                            f'of {product_name} are available.'
                        ),
                        'available_stock': available_stock
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

        # This is a demo payment, not a real payment gateway.
        payment_id = 'PAY-' + uuid.uuid4().hex[:12].upper()

        payment = Payment.objects.create(
            user=current_user,
            payment_id=payment_id,
            payment_method=payment_method,
            amount_paid=str(order.order_total),
            status='Completed'
        )

        order.payment = payment
        order.is_ordered = True
        order.status = 'New'
        order.save(
            update_fields=['payment', 'is_ordered', 'status']
        )

        ordered_items = []

        for cart_item in cart_items:
            product = locked_products[cart_item.product_id]
            variations = list(cart_item.variations.all())

            color = ''
            size = ''

            for variation in variations:
                category = variation.variation_category.lower()

                if category == 'color':
                    color = variation.variation_value
                elif category == 'size':
                    size = variation.variation_value

            order_product = OrderProduct.objects.create(
                order=order,
                payment=payment,
                user=current_user,
                product=product,
                quantity=cart_item.quantity,
                product_price=product.price,
                color=color,
                size=size,
                ordered=True
            )

            order_product.variations.set(variations)

            product.stock -= cart_item.quantity

            if product.stock == 0:
                product.is_available = False

            product.save(
                update_fields=['stock', 'is_available']
            )

            ordered_items.append({
                'order_product_id': order_product.id,
                'product_id': product.id,
                'product_name': product.product_name,
                'price': float(product.price),
                'quantity': cart_item.quantity,
                'subtotal': float(
                    product.price * cart_item.quantity
                ),
                'color': color,
                'size': size,
                'variations': [
                    {
                        'id': variation.id,
                        'category': variation.variation_category,
                        'value': variation.variation_value
                    }
                    for variation in variations
                ]
            })
        generate_vendor_invoices(order)
        
        CartItem.objects.filter(
            id__in=[item.id for item in cart_items]
        ).delete()

        email_subject = 'Order Received - ' + order.order_number

        email_message = render_to_string(
            'orders/order_received_email.html',
            {
                'user': current_user,
                'order': order,
                'payment': payment,
            }
        )

        email = EmailMessage(
            email_subject,
            email_message,
            settings.DEFAULT_FROM_EMAIL,
            [order.email]
        )

        transaction.on_commit(
            lambda: email.send(fail_silently=True)
        )

    return Response(
        {
            'message': 'Demo payment confirmed and order placed successfully.',
            'order': {
                'order_number': order.order_number,
                'payment_id': payment.payment_id,
                'payment_method': payment.payment_method,
                'payment_status': payment.status,
                'amount_paid': float(order.order_total),
                'status': order.status,
                'is_ordered': order.is_ordered,
                'subtotal': float(order.order_total - order.tax),
                'tax': float(order.tax),
                'order_total': float(order.order_total),
                'items': ordered_items
            }
        },
        status=status.HTTP_200_OK
    )



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_order_complete(request, order_number):
    try:
        order = Order.objects.get(
            order_number=order_number,
            user=request.user,
            is_ordered=True
        )
    except Order.DoesNotExist:
        return Response({
            "success": False,
            "message": "Completed order not found."
        }, status=status.HTTP_404_NOT_FOUND)

    payment = order.payment

    ordered_products = OrderProduct.objects.filter(
        order=order,
        user=request.user
    ).select_related('product')

    products = []
    subtotal = 0

    for item in ordered_products:
        item_total = item.product_price * item.quantity
        subtotal += item_total

        products.append({
            "product_name": item.product.product_name,
            "product_price": str(item.product_price),
            "quantity": item.quantity,
            "color": item.color or "",
            "size": item.size or "",
            "total": str(item_total),
        })

    return Response({
        "success": True,
        "order": {
            "order_number": order.order_number,
            "full_name": order.full_name(),
            "full_address": order.full_address(),
            "city": order.city,
            "state": order.state,
            "country": order.country,
            "created_at": order.created_at.isoformat(),
            "status": order.status,
            "subtotal": str(subtotal),
            "tax": str(order.tax),
            "grand_total": str(order.order_total),
        },
        "payment": {
            "payment_id": payment.payment_id if payment else None,
            "payment_method": payment.payment_method if payment else None,
            "status": payment.status if payment else None,
        },
        "products": products,
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def api_admin_orders(request):

    orders = Order.objects.filter(
        is_ordered=True
    ).select_related(
        'user',
        'payment'
    ).order_by('-created_at')

    data = []

    for order in orders:

        items = OrderProduct.objects.filter(
            order=order
        ).select_related(
            'product',
            'user'
        ).prefetch_related(
            'variations'
        )

        order_items = []

        for item in items:

            variations = []

            for variation in item.variations.all():

                variations.append({
                    'id': variation.id,
                    'category': variation.variation_category,
                    'value': variation.variation_value
                })

            order_items.append({

                'order_product_id': item.id,

                'product_id': item.product.id
                if item.product else None,

                'product_name': item.product.product_name
                if item.product else None,

                'vendor_id': (
                    item.product.vendor.id
                    if item.product and item.product.vendor
                    else None
                ),

                'quantity': item.quantity,

                'product_price': item.product_price,

                'subtotal': (
                    item.product_price *
                    item.quantity
                ),

                'color': item.color,
                'size': item.size,

                'variations': variations,

                'ordered': item.ordered
            })

        data.append({

            'order_number': order.order_number,

            'customer': {

                'id': (
                    order.user.id
                    if order.user
                    else None
                ),

                'first_name': order.first_name,
                'last_name': order.last_name,
                'email': order.email,
                'phone': order.phone
            },

            'shipping_address': {

                'address_line_1': order.address_line_1,
                'address_line_2': order.address_line_2,
                'city': order.city,
                'state': order.state,
                'country': order.country
            },

            'order_total': order.order_total,
            'tax': order.tax,

            'status': order.status,
            'is_ordered': order.is_ordered,

            'payment': (
                {
                    'id': order.payment.id,
                    'payment_id': order.payment.payment_id,
                    'payment_method': order.payment.payment_method,
                    'amount_paid': order.payment.amount_paid,
                    'status': order.payment.status,
                    'created_at': order.payment.created_at
                }
                if order.payment
                else None
            ),

            'created_at': order.created_at,
            'updated_at': order.updated_at,

            'items': order_items
        })

    return Response({

        'count': len(data),

        'orders': data

    })

@api_view(['GET'])
@permission_classes([IsAdminUser])
def api_admin_order_detail(request, order_number):

    try:

        order = Order.objects.select_related(
            'user',
            'payment'
        ).get(
            order_number=order_number
        )

    except Order.DoesNotExist:

        return Response(
            {
                'message': 'Order not found.'
            },
            status=status.HTTP_404_NOT_FOUND
        )

    items = OrderProduct.objects.filter(
        order=order
    ).select_related(
        'product'
    ).prefetch_related(
        'variations'
    )

    order_items = []

    for item in items:

        variations = []

        for variation in item.variations.all():

            variations.append({
                'id': variation.id,
                'category': variation.variation_category,
                'value': variation.variation_value
            })

        order_items.append({

            'order_product_id': item.id,

            'product_id': (
                item.product.id
                if item.product
                else None
            ),

            'product_name': (
                item.product.product_name
                if item.product
                else None
            ),

            'vendor_id': (
                item.product.vendor.id
                if item.product and item.product.vendor
                else None
            ),

            'quantity': item.quantity,

            'product_price': item.product_price,

            'subtotal': (
                item.product_price *
                item.quantity
            ),

            'color': item.color,
            'size': item.size,

            'variations': variations,

            'ordered': item.ordered
        })

    return Response({

        'order_number': order.order_number,

        'customer': {

            'id': (
                order.user.id
                if order.user
                else None
            ),

            'first_name': order.first_name,
            'last_name': order.last_name,
            'email': order.email,
            'phone': order.phone
        },

        'shipping_address': {

            'address_line_1': order.address_line_1,
            'address_line_2': order.address_line_2,
            'city': order.city,
            'state': order.state,
            'country': order.country
        },

        'order_total': order.order_total,
        'tax': order.tax,

        'status': order.status,
        'is_ordered': order.is_ordered,

        'payment': (
            {
                'id': order.payment.id,
                'payment_id': order.payment.payment_id,
                'payment_method': order.payment.payment_method,
                'amount_paid': order.payment.amount_paid,
                'status': order.payment.status,
                'created_at': order.payment.created_at
            }
            if order.payment
            else None
        ),

        'items': order_items,

        'created_at': order.created_at,
        'updated_at': order.updated_at
    })

@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def api_admin_order_status(request, order_number):

    try:

        order = Order.objects.get(
            order_number=order_number
        )

    except Order.DoesNotExist:

        return Response(
            {
                'message': 'Order not found.'
            },
            status=status.HTTP_404_NOT_FOUND
        )

    new_status = request.data.get('status')

    allowed_statuses = [
        'New',
        'Accepted',
        'Completed',
        'Cancelled'
    ]

    if new_status not in allowed_statuses:

        return Response(
            {
                'message': 'Invalid order status.',
                'allowed_statuses': allowed_statuses
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    current_status = order.status

    allowed_transitions = {

        'New': [
            'Accepted',
            'Cancelled'
        ],

        'Accepted': [
            'Completed',
            'Cancelled'
        ],

        'Completed': [],

        'Cancelled': []
    }

    if new_status not in allowed_transitions.get(
        current_status,
        []
    ):

        return Response(
            {
                'message': (
                    f'Cannot change order status '
                    f'from {current_status} '
                    f'to {new_status}.'
                )
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    # Restore stock when admin cancels order

    if new_status == 'Cancelled':

        items = OrderProduct.objects.filter(
            order=order
        ).select_related(
            'product'
        )

        for item in items:

            if item.product:

                item.product.stock += item.quantity

                item.product.is_available = (
                    item.product.stock > 0
                )

                item.product.save(
                    update_fields=[
                        'stock',
                        'is_available',
                        'modified_date'
                    ]
                )

    order.status = new_status
    order.save(
        update_fields=[
            'status',
            'updated_at'
        ]
    )

    return Response({

        'message': 'Order status updated successfully.',

        'order_number': order.order_number,

        'old_status': current_status,

        'new_status': order.status
    })

@api_view(['DELETE'])
@permission_classes([IsAdminUser])
def api_admin_order_delete(request, order_number):

    try:

        order = Order.objects.get(
            order_number=order_number
        )

    except Order.DoesNotExist:

        return Response(
            {
                'message': 'Order not found.'
            },
            status=status.HTTP_404_NOT_FOUND
        )

    # Restore stock if order is not already cancelled

    if (
        order.is_ordered
        and order.status != 'Cancelled'
    ):

        items = OrderProduct.objects.filter(
            order=order
        ).select_related(
            'product'
        )

        for item in items:

            if item.product:

                item.product.stock += item.quantity

                item.product.is_available = (
                    item.product.stock > 0
                )

                item.product.save(
                    update_fields=[
                        'stock',
                        'is_available',
                        'modified_date'
                    ]
                )

    order.delete()

    return Response({

        'message': 'Order deleted successfully.',

        'order_number': order_number
    })

@api_view(['GET'])
@permission_classes([IsAdminUser])
def api_admin_payments(request):

    payments = Payment.objects.select_related('user').order_by('-created_at')

    data = []

    for payment in payments:

        order = Order.objects.filter(
            payment=payment
        ).first()

        data.append({
            'payment_id': payment.id,
            'transaction_id': payment.payment_id,
            'payment_method': payment.payment_method,
            'amount_paid': payment.amount_paid,
            'status': payment.status,
            'created_at': payment.created_at,

            'customer': {
                'id': payment.user.id if payment.user else None,
                'first_name': payment.user.first_name if payment.user else None,
                'last_name': payment.user.last_name if payment.user else None,
                'email': payment.user.email if payment.user else None,
            },

            'order': {
                'order_number': order.order_number if order else None,
                'status': order.status if order else None,
                'is_ordered': order.is_ordered if order else None,
            }
        })

    return Response({
        'count': len(data),
        'payments': data
    })

@api_view(['GET'])
@permission_classes([IsAdminUser])
def api_admin_payment_detail(request, payment_id):

    try:
        payment = Payment.objects.select_related('user').get(
            id=payment_id
        )
    except Payment.DoesNotExist:
        return Response(
            {'message': 'Payment not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    order = Order.objects.filter(
        payment=payment
    ).first()

    return Response({

        'payment_id': payment.id,

        'transaction_id': payment.payment_id,

        'payment_method': payment.payment_method,

        'amount_paid': payment.amount_paid,

        'status': payment.status,

        'created_at': payment.created_at,

        'customer': {
            'id': payment.user.id if payment.user else None,
            'first_name': payment.user.first_name if payment.user else None,
            'last_name': payment.user.last_name if payment.user else None,
            'email': payment.user.email if payment.user else None,
            'phone_number': payment.user.phone_number if payment.user else None,
        },

        'order': {
            'order_number': order.order_number if order else None,
            'order_total': order.order_total if order else None,
            'tax': order.tax if order else None,
            'status': order.status if order else None,
            'is_ordered': order.is_ordered if order else None,
            'created_at': order.created_at if order else None,
        }
    })