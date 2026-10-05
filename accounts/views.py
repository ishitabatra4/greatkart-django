from django.shortcuts import render,redirect,get_object_or_404
from accounts.forms import RegistrationForm,UserForm,UserProfileForm,VendorProfileForm
from .models import Account,UserProfile,VendorProfile
from orders.models import Order, OrderProduct
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

from .serializers import RegisterSerializer,VendorProfileSerializer
from .permissions import IsCustomer,IsVendor,IsApprovedVendor
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.encoding import force_str



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
def order_detail(request,order_id):

    order=get_object_or_404(
        Order,
        order_number=order_id,
        user=request.user,
        is_ordered=True
    )

    order_detail=OrderProduct.objects.filter(
        order=order
    )

    subtotal=0

    for i in order_detail:
        subtotal+=i.product_price*i.quantity

    context={
        'order_detail':order_detail,
        'order':order,
        'subtotal':subtotal,
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
@permission_classes([IsCustomer])
def api_order_detail(request,order_number):

    try:

        order=Order.objects.get(
            order_number=order_number,
            user=request.user,
            is_ordered=True
        )

    except Order.DoesNotExist:

        return Response(
            {
                'message':'Order not found.'
            },
            status=status.HTTP_404_NOT_FOUND
        )


    order_products=OrderProduct.objects.filter(
        order=order
    ).select_related(
        'product'
    )


    items=[]

    subtotal=0


    for item in order_products:

        item_subtotal=item.product_price * item.quantity

        subtotal+=item_subtotal


        items.append({
            'order_product_id':item.id,
            'product_id':item.product.id,
            'product_name':item.product.product_name,
            'product_price':item.product_price,
            'quantity':item.quantity,
            'subtotal':item_subtotal,
            'color':item.color,
            'size':item.size,
            'ordered':item.ordered,
        })


    return Response({

        'order':{

            'order_number':order.order_number,

            'customer':{
                'first_name':order.first_name,
                'last_name':order.last_name,
                'email':order.email,
                'phone':order.phone,
            },

            'address':{
                'address_line_1':order.address_line_1,
                'address_line_2':order.address_line_2,
                'city':order.city,
                'state':order.state,
                'country':order.country,
            },

            'order_total':order.order_total,
            'tax':order.tax,
            'subtotal':subtotal,
            'status':order.status,
            'is_ordered':order.is_ordered,
            'created_at':order.created_at,

            'items':items,

        }

    })
class RegisterAPIView(APIView):

    def post(self,request):

        serializer=RegisterSerializer(data=request.data)

        if serializer.is_valid():

            user=serializer.save()

            return Response(
                {
                    'message':'Registration successful. Please activate your account.',
                    'user_id':user.id,
                    'email':user.email,
                    'is_vendor':user.is_vendor
                },
                status=status.HTTP_201_CREATED
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
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

    uid=urlsafe_base64_encode(
        force_bytes(user.pk)
    )

    token=default_token_generator.make_token(user)

    reset_url=(
        f'http://127.0.0.1:8000'
        f'/accounts/reset-password/'
        f'?uid={uid}&token={token}'
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
        order__is_ordered=True
    ).select_related(
        'order',
        'product',
        'user',
        'payment'
    ).order_by('-created_at')

    orders = {}

    for item in order_products:

        order = item.order
        order_number = order.order_number

        if order_number not in orders:

            orders[order_number] = {
                'order_number': order.order_number,

                'customer': {
                    'id': order.user.id,
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

                'items': []
            }

        orders[order_number]['items'].append({

            'order_product_id': item.id,

            'product_id': item.product.id,
            'product_name': item.product.product_name,

            'product_price': item.product_price,
            'quantity': item.quantity,

            'color': item.color,
            'size': item.size,

            'subtotal': float(item.product_price * item.quantity),

            'ordered': item.ordered,
        })

    return Response({
        'count': len(orders),
        'orders': list(orders.values())
    })

@api_view(['GET'])
@permission_classes([IsApprovedVendor])
def api_vendor_order_detail(request, order_number):

    # -------------------------------------------------
    # FIND ONLY THIS VENDOR'S ORDER ITEMS
    # -------------------------------------------------

    order_items = OrderProduct.objects.filter(
        order__order_number=order_number,
        order__is_ordered=True,
        product__vendor=request.user
    ).select_related(
        'order',
        'product',
        'user'
    )


    # -------------------------------------------------
    # ORDER DOES NOT BELONG TO THIS VENDOR
    # -------------------------------------------------

    if not order_items.exists():

        return Response(
            {
                'message': 'Order not found.'
            },
            status=status.HTTP_404_NOT_FOUND
        )


    # -------------------------------------------------
    # GET ORDER
    # -------------------------------------------------

    order = order_items.first().order


    # -------------------------------------------------
    # CALCULATE VENDOR SUBTOTAL
    # -------------------------------------------------

    subtotal = 0

    items = []

    for item in order_items:

        item_subtotal = (
            item.product_price * item.quantity
        )

        subtotal += item_subtotal

        items.append({

            'order_product_id': item.id,

            'product': {
                'id': item.product.id,
                'name': item.product.product_name,
                'price': float(item.product_price),
            },

            'quantity': item.quantity,

            'color': item.color,

            'size': item.size,

            'subtotal': float(item_subtotal),

            'ordered': item.ordered,

            'created_at': item.created_at,
        })


    # -------------------------------------------------
    # RESPONSE
    # -------------------------------------------------

    return Response({

        'order': {

            'order_number': order.order_number,

            'customer': {

                'id': order.user.id,

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


            'order_total': float(order.order_total),

            'tax': float(order.tax),

            'vendor_subtotal': float(subtotal),

            'status': order.status,

            'is_ordered': order.is_ordered,

            'created_at': order.created_at,

            'items': items,
        }

    })