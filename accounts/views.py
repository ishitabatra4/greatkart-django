from django.shortcuts import render,redirect,get_object_or_404
from accounts.forms import RegistrationForm,UserForm,UserProfileForm
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
from django.http import HttpResponse
from carts.views import cart_id
from carts.models import Cart,CartItem
import requests
from django.db.models import Sum,F,FloatField,ExpressionWrapper
from django.utils import timezone
from store.models import Product
from rest_framework.decorators import api_view,permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from .serializers import RegisterSerializer



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

            if registration_type=='vendor':
                user.is_vendor=True
            else:
                user.is_vendor=False

            user.save()

            if registration_type=='vendor':
                VendorProfile.objects.create(
                    user=user,
                    store_name=form.cleaned_data['store_name'],
                    store_description=form.cleaned_data['store_description'],
                    store_logo=form.cleaned_data['store_logo'],
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
                    'token':default_token_generator.make_token(user)
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

    context={
        'orders_count':orders_count,
        'userprofile':userprofile,
    }

    return render(request,'accounts/dashboard.html',context)


def forgotPassword(request):
    if request.method=='POST':
        email=request.POST['email']

        if Account.objects.filter(email=email).exists():
            user=Account.objects.get(email__iexact=email)

            current_site=get_current_site(request)
            mail_subject='Reset your password'

            message=render_to_string(
                'accounts/reset_password_email.html',
                {
                    'user':user,
                    'domain':current_site,
                    'uid':urlsafe_base64_encode(force_bytes(user.pk)),
                    'token':default_token_generator.make_token(user),
                }
            )

            to_email=email

            send_email=EmailMessage(
                mail_subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [to_email]
            )

            send_email.send()

            messages.success(
                request,
                'Password reset email has been sent to your email address'
            )

            return redirect('login')

        else:
            messages.error(request,'Account does not exists!')
            return redirect('forgotPassword')

    return render(request,'accounts/forgotPassword.html')


def resetpassword_validate(request,uidb64,token):
    try:
        uid=urlsafe_base64_decode(uidb64).decode()
        user=Account._default_manager.get(pk=uid)

    except(TypeError,ValueError,OverflowError,Account.DoesNotExist):
        user=None

    if user is not None and default_token_generator.check_token(user,token):
        request.session['uid']=uid

        messages.success(
            request,
            'Please reset your password'
        )

        return redirect('resetPassword')

    else:
        messages.error(
            request,
            'This link has been expired'
        )

        return redirect('login')


def resetPassword(request):
    if request.method=='POST':
        password=request.POST['password']
        confirm_password=request.POST['confirm_password']

        if password==confirm_password:
            uid=request.session.get('uid')
            user=Account.objects.get(pk=uid)

            user.set_password(password)
            user.save()

            messages.success(
                request,
                'Password reset successful'
            )

            return redirect('login')

        else:
            messages.error(
                request,
                'Password do not match'
            )

            return redirect('resetPassword')

    else:
        return render(request,'accounts/resetPassword.html')


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
def edit_profile(request):
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

            return redirect('edit_profile')

    else:
        user_form=UserForm(instance=request.user)
        profile_form=UserProfileForm(instance=userprofile)

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
    order_detail = OrderProduct.objects.filter(order__order_number=order_id)
    order = Order.objects.get(order_number=order_id)
    subtotal = 0
    for i in order_detail:
        subtotal += i.product_price * i.quantity

    context = {
        'order_detail': order_detail,
        'order': order,
        'subtotal': subtotal,
    }
    return render(request, 'accounts/order_detail.html', context)

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

            if registration_type=='vendor':
                user.is_vendor=True
            else:
                user.is_vendor=False

            user.save()

            if registration_type=='vendor':
                VendorProfile.objects.create(
                    user=user,
                    store_name=form.cleaned_data['store_name'],
                    store_description=form.cleaned_data['store_description'],
                    store_logo=form.cleaned_data['store_logo'],
                    is_approved=False
                )

            current_site=get_current_site(request)
            mail_subject='Please activate your account'
            message=render_to_string('accounts/account_verification_email.html',{
                'user':user,
                'domain':current_site,
                'uid':urlsafe_base64_encode(force_bytes(user.pk)),
                'token':default_token_generator.make_token(user),
            })

            send_email=EmailMessage(
                mail_subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [email]
            )
            send_email.send()

            return redirect('/accounts/login/?command=verification&email='+email)

    else:
        form=RegistrationForm()

    context={'form':form}
    return render(request,'accounts/register.html',context)

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
def become_vendor(request):
    if request.user.is_vendor:
        messages.info(request,'You are already registered as a vendor.')
        return redirect('dashboard')

    if request.method=='POST':
        VendorProfile.objects.create(
            user=request.user,
            store_name=request.POST.get('store_name'),
            store_description=request.POST.get('store_description',''),
            is_approved=False
        )

        request.user.is_vendor=True
        request.user.save()

        messages.success(
            request,
            'Vendor application submitted. Please wait for admin approval.'
        )

        return redirect('dashboard')

    return render(request,'accounts/become_vendor.html')

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