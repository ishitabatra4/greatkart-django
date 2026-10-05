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
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from orders.models import Order, OrderProduct
from store.models import Product
from django.db import transaction

import datetime
import datetime
import uuid
TAX_RATE=18


def payments(request):
    return render(request,'orders/payments.html')


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


def order_complete(request,order_number):
    try:
        order=Order.objects.get(
            order_number=order_number,
            user=request.user,
            is_ordered=True
        )
    except Order.DoesNotExist:
        return redirect('store')

    payment=order.payment

    ordered_products=OrderProduct.objects.filter(
        order=order,
        user=request.user
    )

    subtotal=0

    for item in ordered_products:
        subtotal+=item.product_price*item.quantity

    context={
        'order':order,
        'payment':payment,
        'ordered_products':ordered_products,
        'subtotal':subtotal,
    }

    return render(request,'orders/order_complete.html',context)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_place_order(request):

    current_user = request.user

    cart_items = CartItem.objects.filter(
        user=current_user
    ).select_related(
        'product'
    ).prefetch_related(
        'variations'
    )

    if not cart_items.exists():
        return Response(
            {
                'message': 'Your cart is empty.'
            },
            status=status.HTTP_400_BAD_REQUEST
        )

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
                {
                    'message': f'{field} is required.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

    total = 0
    quantity = 0

    for cart_item in cart_items:

        total += (
            cart_item.product.price *
            cart_item.quantity
        )

        quantity += cart_item.quantity

    tax = (total * TAX_RATE) / 100
    grand_total = total + tax

    # Create ONLY the Order
    data = Order()

    data.user = current_user
    data.first_name = request.data.get('first_name')
    data.last_name = request.data.get('last_name')
    data.phone = request.data.get('phone')
    data.email = request.data.get('email')

    data.address_line_1 = request.data.get(
        'address_line_1'
    )

    data.address_line_2 = request.data.get(
        'address_line_2',
        ''
    )

    data.country = request.data.get(
        'country'
    )

    data.state = request.data.get(
        'state'
    )

    data.city = request.data.get(
        'city'
    )

    data.order_note = request.data.get(
        'order_note',
        ''
    )

    data.order_total = grand_total
    data.tax = tax
    data.ip = request.META.get(
        'REMOTE_ADDR'
    )

    # IMPORTANT
    # Order is NOT completed yet
    data.is_ordered = False
    data.status = 'New'

    data.save()

    # Generate order number
    current_date = datetime.date.today().strftime(
        '%Y%m%d'
    )

    order_number = current_date + str(data.id)

    data.order_number = order_number
    data.save()

    items = []

    for cart_item in cart_items:

        variations = list(
            cart_item.variations.all()
        )

        color = ''
        size = ''

        for variation in variations:

            if (
                variation.variation_category.lower()
                == 'color'
            ):
                color = variation.variation_value

            elif (
                variation.variation_category.lower()
                == 'size'
            ):
                size = variation.variation_value

        item_subtotal = (
            cart_item.product.price *
            cart_item.quantity
        )

        items.append(
            {
                'cart_item_id': cart_item.id,
                'product_id': cart_item.product.id,
                'product_name': (
                    cart_item.product.product_name
                ),
                'price': float(
                    cart_item.product.price
                ),
                'quantity': cart_item.quantity,
                'subtotal': float(
                    item_subtotal
                ),
                'color': color,
                'size': size,
                'variations': [
                    {
                        'id': variation.id,
                        'category': (
                            variation.variation_category
                        ),
                        'value': (
                            variation.variation_value
                        )
                    }
                    for variation in variations
                ]
            }
        )

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

    # 1. Validate order
    try:
        order = Order.objects.get(
            order_number=order_number,
            user=current_user,
            is_ordered=False
        )

    except Order.DoesNotExist:
        return Response(
            {
                'message': 'Invalid or already processed order.'
            },
            status=status.HTTP_404_NOT_FOUND
        )

    # 2. Validate payment method
    if not payment_method:
        return Response(
            {
                'message': 'Please select a payment method.'
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    # 3. Check if payment already exists
    if order.payment:
        return Response(
            {
                'message': 'Payment has already been made for this order.'
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    # 4. Get current user's cart
    cart_items = CartItem.objects.filter(
        user=current_user
    ).select_related(
        'product'
    ).prefetch_related(
        'variations'
    )

    if not cart_items.exists():
        return Response(
            {
                'message': 'Your cart is empty.'
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    with transaction.atomic():

        payment_id = (
            'PAY-' +
            uuid.uuid4().hex[:12].upper()
        )

        # 5. Check stock before payment
        for cart_item in cart_items:

            product = (
                cart_item.product.__class__
                .objects
                .select_for_update()
                .get(
                    id=cart_item.product.id
                )
            )

            if product.stock < cart_item.quantity:

                return Response(
                    {
                        'message': (
                            f'Sorry, only '
                            f'{product.stock} item(s) of '
                            f'{product.product_name} '
                            f'are available.'
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

        # 6. Create payment
        payment = Payment.objects.create(
            user=current_user,
            payment_id=payment_id,
            payment_method=payment_method,
            amount_paid=str(order.order_total),
            status='Completed'
        )

        # 7. Update order
        order.payment = payment
        order.is_ordered = True
        order.status = 'New'
        order.save()

        ordered_items = []

        # 8. Create OrderProduct
        for cart_item in cart_items:

            product = (
                cart_item.product.__class__
                .objects
                .select_for_update()
                .get(
                    id=cart_item.product.id
                )
            )

            order_product = OrderProduct()

            order_product.order = order
            order_product.payment = payment
            order_product.user = current_user
            order_product.product = product
            order_product.quantity = cart_item.quantity
            order_product.product_price = product.price
            order_product.ordered = True

            color = ''
            size = ''

            variations = list(
                cart_item.variations.all()
            )

            for item in variations:

                if (
                    item.variation_category.lower()
                    == 'color'
                ):
                    color = item.variation_value

                elif (
                    item.variation_category.lower()
                    == 'size'
                ):
                    size = item.variation_value

            order_product.color = color
            order_product.size = size

            order_product.save()

            # Save all variations
            order_product.variations.set(
                variations
            )

            # 9. Reduce stock
            product.stock -= cart_item.quantity

            if product.stock == 0:
                product.is_available = False

            product.save()

            ordered_items.append(
                {
                    'order_product_id': order_product.id,
                    'product_id': product.id,
                    'product_name': product.product_name,
                    'price': float(product.price),
                    'quantity': cart_item.quantity,
                    'subtotal': float(
                        product.price *
                        cart_item.quantity
                    ),
                    'color': color,
                    'size': size,
                    'variations': [
                        {
                            'id': variation.id,
                            'category': (
                                variation.variation_category
                            ),
                            'value': (
                                variation.variation_value
                            )
                        }
                        for variation in variations
                    ]
                }
            )

        # 10. Delete cart only after successful payment/order creation
        cart_items.delete()

        # 11. Send order email
        email_subject = (
            'Order Received - ' +
            order.order_number
        )

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
            lambda: email.send(
                fail_silently=True
            )
        )

    # 12. API response
    return Response(
        {
            'message': (
                'Payment confirmed and '
                'order placed successfully.'
            ),
            'order': {
                'order_number': order.order_number,
                'payment_id': payment.payment_id,
                'payment_method': payment.payment_method,
                'amount_paid': float(
                    order.order_total
                ),
                'status': order.status,
                'is_ordered': order.is_ordered,
                'subtotal': float(
                    order.order_total - order.tax
                ),
                'tax': float(order.tax),
                'order_total': float(
                    order.order_total
                ),
                'items': ordered_items
            }
        },
        status=status.HTTP_200_OK
    )