from django.shortcuts import render,get_object_or_404,redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.core.paginator import Paginator
from carts.models import CartItem
from carts.views import cart_id
from category.models import Category
from orders.models import OrderProduct
from .models import Product,ReviewRating
from .forms import ReviewForm


def store(request,category_slug=None):
    category=None
    products=None

    if category_slug is not None:
        category=get_object_or_404(Category,slug=category_slug)
        products=Product.objects.filter(category=category,is_available=True)
        paginator=Paginator(products,1)
        page=request.GET.get('page')
        paged_products=paginator.get_page(page)
        product_count=products.count()
    else:
        products=Product.objects.filter(is_available=True).order_by('id')
        paginator=Paginator(products,3)
        page=request.GET.get('page')
        paged_products=paginator.get_page(page)
        product_count=products.count()

    context={
        'products':paged_products,
        'product_count':product_count
    }

    return render(request,'store/store.html',context)


def product_detail(request,category_slug,product_slug):
    single_product=get_object_or_404(
        Product,
        category__slug=category_slug,
        slug=product_slug
    )

    in_cart=CartItem.objects.filter(
        cart__cart_id=cart_id(request),
        product=single_product
    ).exists()

    if request.user.is_authenticated:
        orderproduct=OrderProduct.objects.filter(
            user=request.user,
            product=single_product,
            ordered=True
        ).exists()
    else:
        orderproduct=False

    reviews=ReviewRating.objects.filter(
        product=single_product,
        status=True
    )

    context={
        'single_product':single_product,
        'in_cart':in_cart,
        'orderproduct':orderproduct,
        'reviews':reviews
    }

    return render(request,'store/product_detail.html',context)


def search(request):
    products=Product.objects.none()
    product_count=0

    if 'keyword' in request.GET:
        keyword=request.GET['keyword']

        if keyword:
            products=Product.objects.order_by('-created_date').filter(
                Q(description__icontains=keyword)|
                Q(product_name__icontains=keyword)
            )
            product_count=products.count()

    context={
        'products':products,
        'product_count':product_count
    }

    return render(request,'store/store.html',context)


@login_required(login_url='login')
def submit_review(request,product_id):
    url=request.META.get('HTTP_REFERER')

    if request.method=='POST':
        try:
            review=ReviewRating.objects.get(
                user=request.user,
                product_id=product_id
            )

            form=ReviewForm(request.POST,instance=review)

            if form.is_valid():
                form.save()
                messages.success(
                    request,
                    'Thank you! Your review has been updated.'
                )

        except ReviewRating.DoesNotExist:
            form=ReviewForm(request.POST)

            if form.is_valid():
                data=ReviewRating()
                data.subject=form.cleaned_data['subject']
                data.rating=form.cleaned_data['rating']
                data.review=form.cleaned_data['review']
                data.ip=request.META.get('REMOTE_ADDR')
                data.product_id=product_id
                data.user=request.user
                data.save()

                messages.success(
                    request,
                    'Thank you! Your review has been submitted.'
                )

    return redirect(url)