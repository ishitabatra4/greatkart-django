from django.http import request, response
from django.shortcuts import render,redirect,get_object_or_404
from accounts.forms import RegistrationForm,UserForm,UserProfileForm,VendorProfileForm
from .models import Account,UserProfile,VendorProfile
from orders.models import Order, OrderProduct , VendorInvoice
from django.contrib import messages,auth
from django.contrib.auth.decorators import login_required
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode,urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMessage
from django.conf import settings
from carts.views import cart_id
from carts.models import Cart,CartItem
from django.db.models import Sum,F,FloatField,ExpressionWrapper
from django.utils import timezone
from store.models import Product
from rest_framework.decorators import api_view,permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from django.db import transaction
from django.urls import reverse
from orders.invoice_utils import generate_vendor_invoices

from django.db.models import Q

from .serializers import RegisterSerializer,VendorProfileSerializer
from .permissions import IsCustomer,IsVendor,IsApprovedVendor, IsAdminUser
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.encoding import force_str

from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.exceptions import InvalidToken
from django.views.decorators.csrf import csrf_protect
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie




def register(request):
    if request.method=='POST':
        form=RegistrationForm(request.POST,request.FILES)

        if form.is_valid():
            first_name=form.cleaned_data['first_name']
            last_name=form.cleaned_data['last_name']
            phone_number=form.cleaned_data['phone_number']
            email=form.cleaned_data['email']
            password=form.cleaned_data['password']
            registration_type=form.cleaned_data['registration_type']
            gstin=form.cleaned_data.get('gstin','')

            username=email.split('@')[0]

            if Account.objects.filter(email=email).exists():
                messages.error(request,'An account with this email already exists.')
                return redirect('register')

            if Account.objects.filter(username=username).exists():
                username=username+str(Account.objects.count()+1)

            user=Account.objects.create_user(
                first_name=first_name,
                last_name=last_name,
                email=email,
                username=username,
                password=password
            )

            user.phone_number=phone_number
            user.is_vendor=registration_type=='vendor'
            user.save()

            if registration_type=='vendor':
                VendorProfile.objects.create(
                    user=user,
                    gstin=gstin,
                    is_approved=False
                )

            current_site=get_current_site(request)

            mail_subject='Please activate your account'

            message=render_to_string(
                'accounts/account_verification_email.html',
                {
                    'user':user,
                    'domain':current_site,
                    'uid':urlsafe_base64_encode(force_bytes(user.pk)),
                    'token':default_token_generator.make_token(user),
                }
            )

            send_email=EmailMessage(
                mail_subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [email]
            )

            send_email.send()

            return redirect(
                '/accounts/login/?command=verification&email='+email
            )

    else:
        form=RegistrationForm()

    context={
        'form':form
    }

    return render(request,'accounts/register.html',context)


def login(request):
    if request.method=='POST':
        email=request.POST['email']
        password=request.POST['password']

        user=auth.authenticate(email=email,password=password)

        if user is not None:
            try:
                cart=Cart.objects.get(cart_id=cart_id(request))
                is_cart_item_exists=CartItem.objects.filter(cart=cart).exists()

                if is_cart_item_exists:
                    cart_item=CartItem.objects.filter(cart=cart)

                    product_variation=[]

                    for item in cart_item:
                        variation=item.variations.all()
                        product_variation.append(list(variation))

                    cart_item=CartItem.objects.filter(user=user)

                    ex_var_list=[]
                    id=[]

                    for item in cart_item:
                        existing_variation=item.variations.all()
                        ex_var_list.append(list(existing_variation))
                        id.append(item.id)

                    for pr in product_variation:
                        if pr in ex_var_list:
                            index=ex_var_list.index(pr)
                            item_id=id[index]
                            item=CartItem.objects.get(id=item_id)
                            item.quantity+=1
                            item.user=user
                            item.save()
                        else:
                            cart_item=CartItem.objects.filter(cart=cart)

                            for item in cart_item:
                                item.user=user
                                item.save()

            except:
                pass

            auth.login(request,user)

            messages.success(request,'you are now logged in')

            if user.is_vendor:
                return redirect('vendor_orders')
            else:
                return redirect('home')


        else:
            messages.error(request,'invalid login credentials')
            return redirect('login')

    return render(request,'accounts/login.html')


@login_required(login_url='login')
def logout(request):
    auth.logout(request)
    messages.success(request,'You are logged out.')
    return redirect('login')


def activate(request,uidb64,token):
    try:
        uid=urlsafe_base64_decode(uidb64).decode()
        user=Account._default_manager.get(pk=uid)

    except(TypeError,ValueError,OverflowError,Account.DoesNotExist):
        user=None

    if user is not None and default_token_generator.check_token(user,token):
        user.is_active=True
        user.save()

        messages.success(
            request,
            'Congratulations! Your account is activated.'
        )

        return redirect('login')

    else:
        messages.error(request,'Invalid activation link')
        return redirect('register')


@login_required(login_url='login')
def dashboard(request):

    orders=Order.objects.filter(
        user=request.user,
        is_ordered=True
    ).order_by('-created_at')

    orders_count=orders.count()

    userprofile,created=UserProfile.objects.get_or_create(
        user=request.user
    )

    vendor_profile=None

    if request.user.is_vendor:

        try:
            vendor_profile=VendorProfile.objects.get(
                user=request.user
            )

        except VendorProfile.DoesNotExist:
            vendor_profile=None

    context={
        'orders':orders,
        'orders_count':orders_count,
        'userprofile':userprofile,
        'vendor_profile':vendor_profile,
    }

    return render(
        request,
        'accounts/dashboard.html',
        context
    )



@login_required(login_url='login')
def my_orders(request):
    orders=Order.objects.filter(
        user=request.user,
        is_ordered=True
    ).order_by('-created_at')

    context={
        'orders':orders,
    }

    return render(request,'accounts/my_orders.html',context)

@login_required(login_url='login')
def profile(request):

    user=request.user

    userprofile,created=UserProfile.objects.get_or_create(
        user=user
    )

    vendor_profile=None

    if user.is_vendor:

        try:
            vendor_profile=VendorProfile.objects.get(
                user=user
            )

        except VendorProfile.DoesNotExist:
            vendor_profile=None

    context={
        'userprofile':userprofile,
        'vendor_profile':vendor_profile,
    }

    return render(
        request,
        'accounts/profile.html',
        context
    )
@login_required(login_url='login')
def edit_profile(request):

    if request.user.is_vendor:

        try:
            vendor_profile=request.user.vendorprofile

        except VendorProfile.DoesNotExist:

            messages.error(
                request,
                'Vendor profile not found.'
            )

            return redirect('dashboard')


        if request.method=='POST':

            vendor_form=VendorProfileForm(
                request.POST,
                instance=vendor_profile
            )

            if vendor_form.is_valid():

                vendor_form.save()

                messages.success(
                    request,
                    'Vendor profile updated successfully.'
                )

                return redirect('profile')

        else:

            vendor_form=VendorProfileForm(
                instance=vendor_profile
            )


        return render(
            request,
            'accounts/edit_profile.html',
            {
                'vendor_form':vendor_form
            }
        )


    userprofile,created=UserProfile.objects.get_or_create(
        user=request.user
    )


    if request.method=='POST':

        user_form=UserForm(
            request.POST,
            instance=request.user
        )

        profile_form=UserProfileForm(
            request.POST,
            request.FILES,
            instance=userprofile
        )

        if user_form.is_valid() and profile_form.is_valid():

            user_form.save()
            profile_form.save()

            messages.success(
                request,
                'Your profile has been updated.'
            )

            return redirect('profile')

    else:

        user_form=UserForm(
            instance=request.user
        )

        profile_form=UserProfileForm(
            instance=userprofile
        )


    context={
        'user_form':user_form,
        'profile_form':profile_form,
        'userprofile':userprofile,
    }


    return render(
        request,
        'accounts/edit_profile.html',
        context
    )

@login_required(login_url='login')
def change_password(request):
    if request.method == 'POST':
        current_password = request.POST['current_password']
        new_password = request.POST['new_password']
        confirm_password = request.POST['confirm_password']

        user = Account.objects.get(username__exact=request.user.username)

        if new_password == confirm_password:
            success = user.check_password(current_password)
            if success:
                user.set_password(new_password)
                user.save()
                # auth.logout(request)
                messages.success(request, 'Password updated successfully.')
                return redirect('change_password')
            else:
                messages.error(request, 'Please enter valid current password')
                return redirect('change_password')
        else:
            messages.error(request, 'Password does not match!')
            return redirect('change_password')
    return render(request, 'accounts/change_password.html')

@login_required(login_url='login')
def order_detail(request, order_id):
    order = get_object_or_404(
        Order,
        id=order_id,
        user=request.user,
        is_ordered=True
    )

    ordered_products = list(
        OrderProduct.objects.filter(
            order=order
        ).select_related('product')
    )

    subtotal = 0

    for item in ordered_products:
        item.line_total = item.product_price * item.quantity
        subtotal += item.line_total

    context = {
        'order': order,
        'ordered_products': ordered_products,
        'subtotal': subtotal,
    }

    return render(
        request,
        'accounts/order_detail.html',
        context
    )

@login_required(login_url='login')
def vendor_orders(request):
    if not request.user.is_vendor:
        messages.error(request,'You are not registered as a vendor.')
        return redirect('dashboard')

    try:
        vendor_profile=request.user.vendorprofile
    except VendorProfile.DoesNotExist:
        messages.error(request,'Vendor profile not found.')
        return redirect('dashboard')

    if not vendor_profile.is_approved:
        messages.warning(request,'Your vendor account is waiting for admin approval.')
        return redirect('dashboard')

    orders=OrderProduct.objects.filter(
        product__vendor=request.user,
        order__is_ordered=True
    ).select_related('order','product').order_by('-created_at')

    today=timezone.localdate()

    today_orders=orders.filter(
        created_at__date=today
    )

    orders_count=today_orders.values('order_id').distinct().count()

    today_sales=today_orders.aggregate(
        total=Sum(
            ExpressionWrapper(
                F('product_price')*F('quantity'),
                output_field=FloatField()
            )
        )
    )['total'] or 0

    products=Product.objects.filter(
        vendor=request.user
    ).order_by('-created_date')

    context={
        'orders':orders,
        'products':products,
        'orders_count':orders_count,
        'today_sales':today_sales,
    }

    return render(request,'store/vendor_orders.html',context)


@login_required(login_url='login')
def vendor_invoice_detail(request, invoice_number):
    # Only approved vendors can view vendor invoices.
    if not request.user.is_vendor:
        return redirect('home')

    try:
        vendor_profile = request.user.vendorprofile
    except VendorProfile.DoesNotExist:
        return redirect('vendor_orders')

    if not vendor_profile.is_approved:
        return redirect('vendor_orders')

    invoice = get_object_or_404(
        VendorInvoice.objects.select_related(
            'order', 'vendor'
        ),
        invoice_number=invoice_number,
        vendor=request.user,
        order__is_ordered=True
    )

    invoice_items = invoice.items.filter(
        product__vendor=request.user,
        ordered=True
    ).select_related(
        'product'
    ).prefetch_related(
        'variations'
    )

    if not invoice_items.exists():
        return redirect('vendor_orders')

    # Build invoice lines using this vendor's products only.
    items = []
    for item in invoice_items:
        items.append({
            'product_name': item.product.product_name,
            'quantity': item.quantity,
            'unit_price': item.product_price,
            'subtotal': item.product_price * item.quantity,
            'color': item.color,
            'size': item.size,
        })

    order = invoice.order

    context = {
        'invoice': invoice,
        'order': order,
        'vendor_profile': vendor_profile,
        'items': items,
    }

    return render(
        request,
        'store/vendor_invoice.html',
        context
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_me(request):
    user=request.user

    return Response({
        'id':user.id,
        'first_name':user.first_name,
        'last_name':user.last_name,
        'email':user.email,
        'is_vendor':user.is_vendor,
        'is_active':user.is_active,
    })

@api_view(['GET','PATCH'])
@permission_classes([IsAuthenticated])
def api_profile(request):

    user=request.user

    if request.method=='GET':

        if user.is_vendor:

            try:
                vendor_profile=user.vendorprofile

            except VendorProfile.DoesNotExist:

                return Response(
                    {
                        'message':'Vendor profile not found.'
                    },
                    status=status.HTTP_404_NOT_FOUND
                )

            return Response({
                'id':user.id,
                'first_name':user.first_name,
                'last_name':user.last_name,
                'username':user.username,
                'email':user.email,
                'phone_number':user.phone_number,
                'is_vendor':user.is_vendor,
                'is_active':user.is_active,

                'profile':{
                    'gstin':vendor_profile.gstin,
                    'store_name':vendor_profile.store_name,
                    'business_type':vendor_profile.business_type,
                    'pan':vendor_profile.pan,

                    'address_line_1':vendor_profile.address_line_1,
                    'address_line_2':vendor_profile.address_line_2,
                    'city':vendor_profile.city,
                    'state':vendor_profile.state,
                    'pincode':vendor_profile.pincode,

                    'account_holder_name':vendor_profile.account_holder_name,
                    'account_number':vendor_profile.account_number,
                    'ifsc_code':vendor_profile.ifsc_code,
                    'bank_name':vendor_profile.bank_name,

                    'shipping_method':vendor_profile.shipping_method,
                    'shipping_charges':vendor_profile.shipping_charges,
                    'return_policy':vendor_profile.return_policy,

                    'is_approved':vendor_profile.is_approved,
                }
            })


        userprofile,created=UserProfile.objects.get_or_create(
            user=user
        )

        return Response({
            'id':user.id,
            'first_name':user.first_name,
            'last_name':user.last_name,
            'username':user.username,
            'email':user.email,
            'phone_number':user.phone_number,
            'is_vendor':user.is_vendor,
            'is_active':user.is_active,

            'profile':{
                'address_line_1':userprofile.address_line_1,
                'address_line_2':userprofile.address_line_2,
                'city':userprofile.city,
                'state':userprofile.state,
                'country':userprofile.country,
                'pincode': userprofile.pincode,
                'profile_picture':(
                    userprofile.profile_picture.url
                    if userprofile.profile_picture
                    else None
                ),
            }
        })


    user.first_name=request.data.get(
        'first_name',
        user.first_name
    )

    user.last_name=request.data.get(
        'last_name',
        user.last_name
    )

    user.phone_number=request.data.get(
        'phone_number',
        user.phone_number
    )

    user.save()


    if user.is_vendor:

        try:
            vendor_profile=user.vendorprofile

        except VendorProfile.DoesNotExist:

            return Response(
                {
                    'message':'Vendor profile not found.'
                },
                status=status.HTTP_404_NOT_FOUND
            )

        fields=[
            'gstin',
            'store_name',
            'business_type',
            'pan',
            'address_line_1',
            'address_line_2',
            'city',
            'state',
            'pincode',
            'account_holder_name',
            'account_number',
            'ifsc_code',
            'bank_name',
            'shipping_method',
            'shipping_charges',
            'return_policy',
        ]

        for field in fields:

            if field in request.data:

                setattr(
                    vendor_profile,
                    field,
                    request.data.get(field)
                )

        vendor_profile.save()

        return Response({
            'message':'Vendor profile updated successfully.'
        })


    userprofile,created=UserProfile.objects.get_or_create(
        user=user
    )

    fields=[
        'address_line_1',
        'address_line_2',
        'city',
        'state',
        'country',
    ]

    for field in fields:

        if field in request.data:

            setattr(
                userprofile,
                field,
                request.data.get(field)
            )

    if 'profile_picture' in request.FILES:

        userprofile.profile_picture=request.FILES['profile_picture']

    userprofile.save()

    return Response({
        'message':'Profile updated successfully.'
    })

@api_view(['GET'])
@permission_classes([IsCustomer])
def api_customer_test(request):

    return Response({
        'message':'Customer authorization successful.',
        'email':request.user.email
    })

@api_view(['GET'])
@permission_classes([IsApprovedVendor])
def api_vendor_test(request):

    return Response({
        'message':'Vendor authorization successful.',
        'email':request.user.email
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_change_password(request):

    user=request.user

    current_password=request.data.get('current_password')
    new_password=request.data.get('new_password')
    confirm_password=request.data.get('confirm_password')

    if not current_password:
        return Response(
            {'message':'Current password is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if not new_password:
        return Response(
            {'message':'New password is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if not confirm_password:
        return Response(
            {'message':'Confirm password is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if not user.check_password(current_password):
        return Response(
            {'message':'Please enter valid current password.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if new_password!=confirm_password:
        return Response(
            {'message':'Password does not match!'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if current_password==new_password:
        return Response(
            {'message':'New password must be different from current password.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        validate_password(new_password,user)

    except ValidationError as e:
        return Response(
            {'message':e.messages},
            status=status.HTTP_400_BAD_REQUEST
        )

    user.set_password(new_password)
    user.save()

    return Response({
        'message':'Password updated successfully.'
    })

@api_view(['GET'])
@permission_classes([IsCustomer])
def api_my_orders(request):

    orders=Order.objects.filter(
        user=request.user,
        is_ordered=True
    ).order_by('-created_at')

    data=[]

    for order in orders:

        data.append({
            'id': order.id,
            'order_number':order.order_number,
            'first_name':order.first_name,
            'last_name':order.last_name,
            'phone':order.phone,
            'email':order.email,
            'order_total':order.order_total,
            'tax':order.tax,
            'status':order.status,
            'is_ordered':order.is_ordered,
            'created_at':order.created_at,
        })

    return Response({
        'count':orders.count(),
        'orders':data
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_order_detail(request, order_number):
    try:
        order = Order.objects.get(
            Q(order_number=str(order_number)) | Q(id=order_number),
            user=request.user,
            is_ordered=True
        )
    except (Order.DoesNotExist, ValueError, TypeError):
        return Response(
            {'message': 'Order not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    order_products = (
        OrderProduct.objects.filter(order=order)
        .select_related('product', 'payment')
        .prefetch_related('variations')
    )

    items = []
    subtotal = 0

    for item in order_products:
        item_subtotal = item.product_price * item.quantity
        subtotal += item_subtotal

        items.append({
            'order_product_id': item.id,
            'product_id': item.product.id,
            'product_name': item.product.product_name,
            'product_price': item.product_price,
            'quantity': item.quantity,
            'subtotal': item_subtotal,
            'color': item.color,
            'size': item.size,
            'ordered': item.ordered,
            'vendor_invoice_id': item.vendor_invoice_id,
        })

    # Fetch invoices belonging to this customer's order only.
    invoices_queryset = (
        VendorInvoice.objects.filter(order=order)
        .select_related('vendor')
        .prefetch_related('items__product', 'items__variations')
        .order_by('id')
    )

    vendor_invoices = []

    for invoice in invoices_queryset:
        vendor = invoice.vendor

        if vendor:
            vendor_name = (
                f"{getattr(vendor, 'first_name', '')} "
                f"{getattr(vendor, 'last_name', '')}"
            ).strip()

            if not vendor_name:
                vendor_name = (
                    getattr(vendor, 'username', None)
                    or f"Vendor #{vendor.pk}"
                )
        else:
            vendor_name = 'Platform / Unassigned'

        invoice_items = []

        for item in invoice.items.all():
            invoice_items.append({
                'order_product_id': item.id,
                'product_id': item.product_id,
                'product_name': item.product.product_name,
                'product_price': item.product_price,
                'quantity': item.quantity,
                'subtotal': round(
                    float(item.product_price) * item.quantity, 2
                ),
                'color': item.color,
                'size': item.size,
            })

        vendor_invoices.append({
            'id': invoice.id,
            'invoice_number': invoice.invoice_number,
            'vendor_id': invoice.vendor_id,
            'vendor_name': vendor_name,
            'subtotal': invoice.subtotal,
            'tax': invoice.tax,
            'total': invoice.total,
            'status': invoice.status,
            'created_at': invoice.created_at,
            'items': invoice_items,
        })

    payment = order.payment

    return Response({
        'order': {
            'id': order.id,
            'order_number': order.order_number,
            'customer': {
                'first_name': order.first_name,
                'last_name': order.last_name,
                'email': order.email,
                'phone': order.phone,
            },
            'address': {
                'address_line_1': order.address_line_1,
                'address_line_2': order.address_line_2,
                'city': order.city,
                'state': order.state,
                'country': order.country,
            },
            'order_total': order.order_total,
            'tax': order.tax,
            'subtotal': subtotal,
            'status': order.status,
            'is_ordered': order.is_ordered,
            'created_at': order.created_at,
            'payment': {
                'payment_id': payment.payment_id,
                'status': payment.status,
                'payment_method': payment.payment_method,
            } if payment else None,
            'items': items,
            'vendor_invoices': vendor_invoices,
        }
    })



class RegisterAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            with transaction.atomic():
                user = serializer.save()

                current_site = get_current_site(request)

                uid = urlsafe_base64_encode(force_bytes(user.pk))
                token = default_token_generator.make_token(user)

                mail_subject = 'Please activate your account'

                message = render_to_string(
                    'accounts/account_verification_email.html',
                    {
                        'user': user,
                        'domain': current_site.domain,
                        'uid': uid,
                        'token': token,
                    }
                )

                email = EmailMessage(
                    mail_subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email]
                )
                email.content_subtype = 'html'
                email.send(fail_silently=False)

        except Exception:
            return Response(
                {
                    'message': (
                        'Registration could not be completed. '
                        'Please try again.'
                    )
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(
            {
                'message': (
                    'Registration successful. '
                    'Please check your email to activate your account.'
                ),
                'email': user.email,
                'is_vendor': user.is_vendor,
            },
            status=status.HTTP_201_CREATED
        )


@api_view(['GET','PATCH'])
@permission_classes([IsVendor])
def api_vendor_profile(request):

    try:
        vendor_profile=request.user.vendorprofile

    except VendorProfile.DoesNotExist:
        return Response(
            {'message':'Vendor profile not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    if request.method=='GET':

        serializer=VendorProfileSerializer(
            vendor_profile
        )

        return Response(serializer.data)

    serializer=VendorProfileSerializer(
        vendor_profile,
        data=request.data,
        partial=True
    )

    if serializer.is_valid():
        serializer.save()

        return Response({
            'message':'Vendor profile updated successfully.',
            'profile':serializer.data
        })

    return Response(
        serializer.errors,
        status=status.HTTP_400_BAD_REQUEST
    )


@api_view(['POST'])
def api_forgot_password(request):

    email=request.data.get('email')

    if not email:
        return Response(
            {'message':'Email is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        user=Account.objects.get(email__iexact=email)

    except Account.DoesNotExist:
        return Response(
            {'message':'No account found with this email.'},
            status=status.HTTP_404_NOT_FOUND
        )

   
    uid = urlsafe_base64_encode(
        force_bytes(user.pk)
    )

    token = default_token_generator.make_token(user)

    from django.urls import reverse
    from django.utils.http import urlencode

    reset_path = reverse('reset_password')

    query_string = urlencode({
        'uid': uid,
        'token': token,
    })

    reset_url = request.build_absolute_uri(
        f'{reset_path}?{query_string}'
    )


    mail_subject='Reset your password'

    message=render_to_string(
        'accounts/reset_password_email.html',
        {
            'user':user,
            'reset_url':reset_url,
        }
    )

    send_email=EmailMessage(
        mail_subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email]
    )

    send_email.content_subtype='html'

    send_email.send()

    return Response({
        'message':'Password reset email has been sent.'
    })


@api_view(['POST'])
def api_reset_password(request):

    uid=request.data.get('uid')
    token=request.data.get('token')
    password=request.data.get('password')
    confirm_password=request.data.get('confirm_password')

    if not uid or not token:
        return Response(
            {'message':'Invalid reset link.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if not password or not confirm_password:
        return Response(
            {'message':'Password and confirm password are required.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if password!=confirm_password:
        return Response(
            {'message':'Passwords do not match.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        uid=force_str(
            urlsafe_base64_decode(uid)
        )

        user=Account.objects.get(pk=uid)

    except(
        TypeError,
        ValueError,
        OverflowError,
        Account.DoesNotExist
    ):
        return Response(
            {'message':'Invalid reset link.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if not default_token_generator.check_token(user,token):
        return Response(
            {'message':'This reset link is invalid or has expired.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        validate_password(
            password,
            user=user
        )

    except ValidationError as e:
        return Response(
            {'password':e.messages},
            status=status.HTTP_400_BAD_REQUEST
        )

    user.set_password(password)
    user.save()

    return Response({
        'message':'Password reset successful.'
    })

def forgot_password(request):

    return render(
        request,
        'accounts/forgot_password.html'
    )


def reset_password(request):

    return render(
        request,
        'accounts/reset_password.html'
    )


@api_view(['GET'])
@permission_classes([IsApprovedVendor])
def api_vendor_orders(request):
    order_products = OrderProduct.objects.filter(
        product__vendor=request.user,
        order__is_ordered=True,
        ordered=True
    ).select_related(
        'order', 'product', 'vendor_invoice'
    ).order_by('-created_at')

    orders = {}

    for item in order_products:
        order = item.order
        order_number = order.order_number

        if order_number not in orders:
            invoice = item.vendor_invoice

            orders[order_number] = {
                'order_number': order_number,
                'customer': {
                    'id': order.user_id,
                    'first_name': order.first_name,
                    'last_name': order.last_name,
                    'email': order.email,
                    'phone': order.phone,
                },
                'shipping_address': {
                    'address_line_1': order.address_line_1,
                    'address_line_2': order.address_line_2,
                    'city': order.city,
                    'state': order.state,
                    'country': order.country,
                },
                'order_total': float(order.order_total or 0),
                'tax': float(order.tax or 0),
                'status': invoice.status if invoice else order.status,
                'invoice_number': invoice.invoice_number if invoice else None,
                'invoice_subtotal': float(invoice.subtotal) if invoice else 0,
                'invoice_tax': float(invoice.tax) if invoice else 0,
                'invoice_total': float(invoice.total) if invoice else 0,
                'invoice_url': (
                    reverse(
                        'vendor_invoice_detail',
                        kwargs={'invoice_number': invoice.invoice_number}
                    )
                    if invoice else None
                ),
                'is_ordered': order.is_ordered,
                'created_at': order.created_at,
                'items': [],
            }

        orders[order_number]['items'].append({
            'order_product_id': item.id,
            'product_id': item.product_id,
            'product_name': item.product.product_name,
            'product_price': float(item.product_price),
            'quantity': item.quantity,
            'color': item.color,
            'size': item.size,
            'subtotal': float(item.product_price * item.quantity),
            'ordered': item.ordered,
        })

    return Response({
        'count': len(orders),
        'orders': list(orders.values()),
    })



@api_view(['GET'])
@permission_classes([IsApprovedVendor])
def api_vendor_order_detail(request, order_number):
    order_items = OrderProduct.objects.filter(
        order__order_number=order_number,
        order__is_ordered=True,
        ordered=True,
        product__vendor=request.user
    ).select_related(
        'order', 'product', 'vendor_invoice'
    ).prefetch_related('variations')

    if not order_items.exists():
        return Response(
            {'message': 'Order not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    order = order_items.first().order

    # Fetch only this vendor's invoice.
    invoice = VendorInvoice.objects.filter(
        order=order,
        vendor=request.user
    ).first()

    # Repair invoice linkage if an invoice is missing.
    if invoice is None:
        generate_vendor_invoices(order)
        invoice = VendorInvoice.objects.filter(
            order=order,
            vendor=request.user
        ).first()

    items = []

    for item in order_items:
        items.append({
            'order_product_id': item.id,
            'product': {
                'id': item.product_id,
                'name': item.product.product_name,
                'price': float(item.product_price),
            },
            'quantity': item.quantity,
            'color': item.color,
            'size': item.size,
            'subtotal': float(item.product_price * item.quantity),
            'ordered': item.ordered,
            'created_at': item.created_at,
        })

    return Response({
        'order': {
            'order_number': order.order_number,
            'customer': {
                'id': order.user_id,
                'first_name': order.first_name,
                'last_name': order.last_name,
                'email': order.email,
                'phone': order.phone,
            },
            'shipping_address': {
                'address_line_1': order.address_line_1,
                'address_line_2': order.address_line_2,
                'city': order.city,
                'state': order.state,
                'country': order.country,
            },
            'order_total': float(order.order_total or 0),
            'tax': float(order.tax or 0),
            'vendor_subtotal': float(invoice.subtotal) if invoice else 0,
            'invoice': {
                'invoice_number': invoice.invoice_number,
                'subtotal': float(invoice.subtotal),
                'tax': float(invoice.tax),
                'total': float(invoice.total),
                'status': invoice.status,
                'url': reverse(
                    'vendor_invoice_detail',
                    kwargs={'invoice_number': invoice.invoice_number}
                ),
            } if invoice else None,
            'status': invoice.status if invoice else order.status,
            'order_status': order.status,
            'is_ordered': order.is_ordered,
            'created_at': order.created_at,
            'items': items,
        }
    })



@api_view(['PATCH'])
@permission_classes([IsApprovedVendor])
def api_vendor_update_order_status(request, order_number):
    current_user = request.user

    try:
        order = Order.objects.get(
            order_number=order_number,
            is_ordered=True
        )
    except Order.DoesNotExist:
        return Response(
            {'message': 'Order not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    # Find only this vendor's invoice for this order.
    invoice = VendorInvoice.objects.filter(
        order=order,
        vendor=current_user
    ).first()

    if invoice is None:
        # Check whether the vendor actually has items in this order.
        vendor_items = OrderProduct.objects.filter(
            order=order,
            product__vendor=current_user,
            ordered=True
        )

        if not vendor_items.exists():
            return Response(
                {'message': 'You are not authorized to update this order.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Create/link invoices if this order has not been invoiced yet.
        generate_vendor_invoices(order)

        invoice = VendorInvoice.objects.filter(
            order=order,
            vendor=current_user
        ).first()

    if invoice is None:
        return Response(
            {'message': 'Vendor invoice could not be found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    new_status = request.data.get('status')

    allowed_statuses = ['Accepted', 'Completed', 'Cancelled']

    if new_status not in allowed_statuses:
        return Response(
            {
                'message': (
                    'Invalid status. Choose from '
                    'Accepted, Completed or Cancelled.'
                )
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    current_status = invoice.status

    allowed_transitions = {
        'New': ['Accepted', 'Cancelled'],
        'Accepted': ['Completed', 'Cancelled'],
        'Completed': [],
        'Cancelled': [],
    }

    if new_status not in allowed_transitions.get(current_status, []):
        return Response(
            {
                'message': (
                    f'Invoice cannot be changed from '
                    f'{current_status} to {new_status}.'
                )
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    # Update only this vendor's invoice.
    invoice.status = new_status
    invoice.save(update_fields=['status', 'updated_at'])

    # Deliberately do not update order.status here.
    return Response(
        {
            'message': 'Vendor invoice status updated successfully.',
            'order': {
                'order_number': order.order_number,
                'status': invoice.status,
                'order_status': order.status,
                'is_ordered': order.is_ordered,
                'invoice_number': invoice.invoice_number,
            }
        },
        status=status.HTTP_200_OK
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_cancel_order(request, order_number):

    current_user = request.user

    # Only customers can cancel orders
    if current_user.is_vendor:
        return Response(
            {'message': 'Only customers can cancel orders.'},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        order = Order.objects.get(
            order_number=order_number,
            user=current_user,
            is_ordered=True
        )
    except Order.DoesNotExist:
        return Response(
            {'message': 'Order not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    # Allowed cancellation statuses
    if order.status not in ['New', 'Accepted']:
        return Response(
            {
                'message': f'Order cannot be cancelled because its current status is {order.status}.'
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    with transaction.atomic():

        # Lock order so two cancellation requests cannot happen together
        order = Order.objects.select_for_update().get(
            id=order.id
        )

        # Re-check status after acquiring lock
        if order.status not in ['New', 'Accepted']:
            return Response(
                {
                    'message': f'Order cannot be cancelled because its current status is {order.status}.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get all products belonging to this order
        order_products = OrderProduct.objects.filter(
            order=order
        ).select_related('product')

        for order_product in order_products:

            # Lock product row before changing stock
            product = Product.objects.select_for_update().get(
                id=order_product.product.id
            )

            # Restore stock
            product.stock += order_product.quantity

            # Product becomes available again
            if product.stock > 0:
                product.is_available = True

            product.save()

        # Cancel order
        order.status = 'Cancelled'
        order.save(update_fields=['status', 'updated_at'])

    return Response(
        {
            'message': 'Order cancelled successfully.',
            'order': {
                'order_number': order.order_number,
                'status': order.status,
                'is_ordered': order.is_ordered
            }
        },
        status=status.HTTP_200_OK
    )

# =========================================================
# ADMIN JWT APIs
# =========================================================
@api_view(['GET','PATCH','DELETE'])
@permission_classes([IsAdminUser])
def api_admin_user_detail(request,user_id):

    try:
        user=Account.objects.get(id=user_id)
    except Account.DoesNotExist:
        return Response(
            {'message':'User not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    if request.method == 'GET':

        return Response({

            'id':user.id,

            'first_name':user.first_name,

            'last_name':user.last_name,

            'username':user.username,

            'email':user.email,

            'phone_number':user.phone_number,

            'is_active':user.is_active,

            'is_vendor':user.is_vendor,

            'is_admin':user.is_admin,

            'date_joined':user.date_joined,

        })

    if request.method == 'PATCH':

        if 'first_name' in request.data:
            user.first_name=request.data['first_name']

        if 'last_name' in request.data:
            user.last_name=request.data['last_name']

        if 'username' in request.data:
            user.username=request.data['username']

        if 'email' in request.data:
            user.email=request.data['email']

        if 'phone_number' in request.data:
            user.phone_number=request.data['phone_number']

        if 'is_active' in request.data:
            user.is_active=request.data['is_active']

        if 'is_vendor' in request.data:
            user.is_vendor=request.data['is_vendor']

        if 'is_admin' in request.data:
            user.is_admin=request.data['is_admin']

        user.save()

        return Response({

            'message':'User updated successfully.',

            'user':{

                'id':user.id,

                'first_name':user.first_name,

                'last_name':user.last_name,

                'username':user.username,

                'email':user.email,

                'phone_number':user.phone_number,

                'is_active':user.is_active,

                'is_vendor':user.is_vendor,

                'is_admin':user.is_admin,

            }

        })

    if request.method == 'DELETE':

        if user.id == request.user.id:

            return Response(
                {'message':'Admin cannot delete their own account.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.delete()

        return Response({
            'message':'User deleted successfully.'
        })


@api_view(['GET','PATCH','DELETE'])
@permission_classes([IsAdminUser])
def api_admin_vendor_detail(request,vendor_id):

    try:
        vendor=VendorProfile.objects.select_related(
            'user'
        ).get(
            user_id=vendor_id
        )

    except VendorProfile.DoesNotExist:

        return Response(
            {'message':'Vendor not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    user=vendor.user

    if request.method == 'GET':

        return Response({

            'vendor_id':user.id,

            'account':{

                'first_name':user.first_name,

                'last_name':user.last_name,

                'username':user.username,

                'email':user.email,

                'phone_number':user.phone_number,

                'is_active':user.is_active,

                'is_vendor':user.is_vendor,

                'is_admin':user.is_admin,

                'date_joined':user.date_joined,

            },

            'vendor_profile':{

                'gstin':vendor.gstin,

                'store_name':vendor.store_name,

                'business_type':vendor.business_type,

                'pan':vendor.pan,

                'address_line_1':vendor.address_line_1,

                'address_line_2':vendor.address_line_2,

                'city':vendor.city,

                'state':vendor.state,

                'pincode':vendor.pincode,

                'account_holder_name':vendor.account_holder_name,

                'account_number':vendor.account_number,

                'ifsc_code':vendor.ifsc_code,

                'bank_name':vendor.bank_name,

                'shipping_method':vendor.shipping_method,

                'shipping_charges':vendor.shipping_charges,

                'return_policy':vendor.return_policy,

                'is_approved':vendor.is_approved,

                'created_at':vendor.created_at,

            }

        })

    if request.method == 'PATCH':

        account_fields=[

            'first_name',

            'last_name',

            'username',

            'email',

            'phone_number',

            'is_active',

        ]

        vendor_fields=[

            'gstin',

            'store_name',

            'business_type',

            'pan',

            'address_line_1',

            'address_line_2',

            'city',

            'state',

            'pincode',

            'account_holder_name',

            'account_number',

            'ifsc_code',

            'bank_name',

            'shipping_method',

            'shipping_charges',

            'return_policy',

        ]

        for field in account_fields:

            if field in request.data:

                setattr(
                    user,
                    field,
                    request.data.get(field)
                )

        for field in vendor_fields:

            if field in request.data:

                setattr(
                    vendor,
                    field,
                    request.data.get(field)
                )

        user.save()

        vendor.save()

        return Response({

            'message':'Vendor updated successfully.',

            'vendor_id':user.id,

            'is_approved':vendor.is_approved,

        })

    if request.method == 'DELETE':

        if user.id == request.user.id:

            return Response(
                {
                    'message':'Admin cannot delete their own account.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        user.delete()

        return Response({

            'message':'Vendor deleted successfully.'

        })
@api_view(['GET'])
@permission_classes([IsAdminUser])
def api_admin_vendors(request):

    status_filter = request.GET.get('status')

    vendors = VendorProfile.objects.select_related(
        'user'
    ).order_by('-created_at')

    # Pending vendors only
    if status_filter == 'pending':
        vendors = vendors.filter(is_approved=False)

    data = []

    for vendor in vendors:

        data.append({
            'vendor_id': vendor.user.id,

            'name': (
                vendor.user.first_name
                + ' '
                + vendor.user.last_name
            ).strip(),

            'email': vendor.user.email,

            'phone': vendor.user.phone_number,

            'is_vendor': vendor.user.is_vendor,

            'is_active': vendor.user.is_active,

            'is_approved': vendor.is_approved,

            'store_name': vendor.store_name,

            'gstin': vendor.gstin,

            'city': vendor.city,

            'state': vendor.state,

            'created_at': vendor.created_at,
        })

    return Response({
        'count': len(data),
        'vendors': data
    })

@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def api_admin_vendor_approval(request, vendor_id):

    try:

        vendor = VendorProfile.objects.select_related(
            'user'
        ).get(
            user_id=vendor_id
        )

    except VendorProfile.DoesNotExist:

        return Response(
            {
                'message': 'Vendor not found.'
            },
            status=status.HTTP_404_NOT_FOUND
        )

    is_approved = request.data.get('is_approved')

    if is_approved is None:

        return Response(
            {
                'message': 'is_approved is required.'
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    if not isinstance(is_approved, bool):

        return Response(
            {
                'message': 'is_approved must be true or false.'
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    vendor.is_approved = is_approved
    vendor.save()

    return Response({

        'message': (
            'Vendor approved successfully.'
            if is_approved
            else 'Vendor rejected successfully.'
        ),

        'vendor': {
            'id': vendor.user.id,
            'email': vendor.user.email,
            'is_approved': vendor.is_approved,
        }

    })

@api_view(['GET', 'POST'])
@permission_classes([IsAdminUser])
def api_admin_users(request):

    # =========================
    # GET ALL USERS
    # =========================
    if request.method == 'GET':

        users = Account.objects.all().order_by('-date_joined')

        data = []

        for user in users:
            data.append({
                'id': user.id,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'username': user.username,
                'email': user.email,
                'phone_number': user.phone_number,
                'is_active': user.is_active,
                'is_vendor': user.is_vendor,
                'is_admin': user.is_admin,
                'date_joined': user.date_joined,
            })

        return Response({
            'count': len(data),
            'users': data
        })


    # =========================
    # CREATE USER
    # =========================
    if request.method == 'POST':

        first_name = request.data.get('first_name', '').strip()
        last_name = request.data.get('last_name', '').strip()
        username = request.data.get('username', '').strip()
        email = request.data.get('email', '').strip()
        phone_number = request.data.get('phone_number', '').strip()
        password = request.data.get('password')

        is_vendor = request.data.get('is_vendor', False)

        # Required fields
        if not username or not email or not password:
            return Response({
                'message': 'Username, email and password are required.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Duplicate username
        if Account.objects.filter(username=username).exists():
            return Response({
                'message': 'Username already exists.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Duplicate email
        if Account.objects.filter(email=email).exists():
            return Response({
                'message': 'Email already exists.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Create account
        user = Account(
            first_name=first_name,
            last_name=last_name,
            username=username,
            email=email,
            phone_number=phone_number,
            is_vendor=is_vendor,
            is_active=True,
            is_admin=False
        )

        # IMPORTANT: hash password
        user.set_password(password)

        user.save()

        # If admin creates vendor, create VendorProfile
        if is_vendor:
            VendorProfile.objects.create(
                user=user
            )

        return Response({
            'message': 'User created successfully.',
            'user': {
                'id': user.id,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'username': user.username,
                'email': user.email,
                'phone_number': user.phone_number,
                'is_active': user.is_active,
                'is_vendor': user.is_vendor,
                'is_admin': user.is_admin,
                'date_joined': user.date_joined,
            }
        }, status=status.HTTP_201_CREATED)

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
        )

        order_items = []

        for item in items:

            order_items.append({

                'order_product_id': item.id,

                'product_id': item.product.id,

                'product_name': item.product.product_name,

                'vendor_id': item.product.vendor.id
                if item.product.vendor
                else None,

                'quantity': item.quantity,

                'product_price': item.product_price,

                'subtotal': (
                    item.product_price
                    * item.quantity
                ),

                'color': item.color,

                'size': item.size,

                'ordered': item.ordered,

            })

        data.append({

            'order_number': order.order_number,

            'customer': {

                'id': order.user.id
                if order.user
                else None,

                'first_name': order.first_name,

                'last_name': order.last_name,

                'email': order.email,

                'phone': order.phone,

            },

            'shipping_address': {

                'address_line_1': order.address_line_1,

                'address_line_2': order.address_line_2,

                'city': order.city,

                'state': order.state,

                'country': order.country,

            },

            'order_total': order.order_total,

            'tax': order.tax,

            'status': order.status,

            'is_ordered': order.is_ordered,

            'created_at': order.created_at,

            'items': order_items,

        })

    return Response({

        'count': len(data),

        'orders': data

    })

@api_view(['GET'])
@permission_classes([IsAdminUser])
def api_admin_products(request):

    products = Product.objects.select_related(
        'vendor',
        'category'
    ).order_by('-created_date')

    data = []

    for product in products:

        data.append({

            'id': product.id,

            'product_name': product.product_name,

            'slug': product.slug,

            'price': product.price,

            'stock': product.stock,

            'is_available': product.is_available,

            'category': {

                'id': product.category.id
                if product.category
                else None,

                'name': product.category.category_name
                if product.category
                else None,

            },

            'vendor': {

                'id': product.vendor.id
                if product.vendor
                else None,

                'email': product.vendor.email
                if product.vendor
                else None,

            },

            'created_date': product.created_date,

        })

    return Response({

        'count': len(data),

        'products': data

    })

@api_view(['GET'])
@permission_classes([IsAdminUser])
def api_admin_dashboard(request):

    total_users=Account.objects.count()

    total_customers=Account.objects.filter(
        is_vendor=False,
        is_admin=False
    ).count()

    total_vendors=Account.objects.filter(
        is_vendor=True
    ).count()

    pending_vendors=VendorProfile.objects.filter(
        is_approved=False
    ).count()

    approved_vendors=VendorProfile.objects.filter(
        is_approved=True
    ).count()

    total_products=Product.objects.count()

    total_orders=Order.objects.filter(
        is_ordered=True
    ).count()

    pending_orders=Order.objects.filter(
        is_ordered=True,
        status='New'
    ).count()

    completed_orders=Order.objects.filter(
        is_ordered=True,
        status='Completed'
    ).count()

    cancelled_orders=Order.objects.filter(
        is_ordered=True,
        status='Cancelled'
    ).count()

    total_sales=Order.objects.filter(
        is_ordered=True
    ).aggregate(
        total=Sum('order_total')
    )['total'] or 0

    return Response({

        'users':total_users,

        'customers':total_customers,

        'vendors':total_vendors,

        'approved_vendors':approved_vendors,

        'pending_vendors':pending_vendors,

        'products':total_products,

        'orders':total_orders,

        'pending_orders':pending_orders,

        'completed_orders':completed_orders,

        'cancelled_orders':cancelled_orders,

        'total_sales':total_sales,

    })

@method_decorator(csrf_protect, name='dispatch')
class CookieTokenObtainPairView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = TokenObtainPairSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        access_token = serializer.validated_data['access']
        refresh_token = serializer.validated_data['refresh']

        response = Response({
            'access': str(access_token),
        })

        response.set_cookie(
            key='refresh_token',
            value=str(refresh_token),
            httponly=True,
            secure=not settings.DEBUG,
            samesite='Lax',
            max_age=7 * 24 * 60 * 60,
            path='/accounts/api/',
        )
        print("JWT LOGIN — refresh cookie set:", response.cookies.get("refresh_token"))
        print("JWT LOGIN — cookie path:", response.cookies["refresh_token"]["path"])

        return response

@method_decorator(csrf_protect, name='dispatch')
class CookieTokenRefreshView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.COOKIES.get('refresh_token')
        print("JWT REFRESH — received cookie:", bool(refresh_token))
        print("JWT REFRESH — request cookies:", list(request.COOKIES.keys()))

        if not refresh_token:
            return Response(
                {'detail': 'Refresh token missing. Please log in again.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        serializer = TokenRefreshSerializer(
            data={'refresh': refresh_token}
        )

        try:
            serializer.is_valid(raise_exception=True)
        except Exception:
            response = Response(
                {'detail': 'Session expired. Please log in again.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )
            response.delete_cookie('refresh_token', path='/accounts/api/')
            return response

        data = serializer.validated_data
        response = Response({'access': data['access']})

        if 'refresh' in data:
            response.set_cookie(
                key='refresh_token',
                value=data['refresh'],
                httponly=True,
                secure=not settings.DEBUG,
                samesite='Lax',
                max_age=7 * 24 * 60 * 60,
                path='/accounts/api/',
            )

        return response

@method_decorator(csrf_protect, name='dispatch')
class CookieTokenLogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.COOKIES.get('refresh_token')

        if refresh_token:
            try:
                RefreshToken(refresh_token).blacklist()
            except TokenError:
                pass

        response = Response({'detail': 'Logged out successfully.'})
        response.delete_cookie('refresh_token', path='/accounts/api/')
        return response


@ensure_csrf_cookie
@api_view(['GET'])
@permission_classes([AllowAny])
def api_csrf(request):
    return Response({'detail': 'CSRF cookie set.'})
