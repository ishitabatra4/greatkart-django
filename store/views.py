from django.shortcuts import render,get_object_or_404,redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.core.paginator import Paginator
from carts.models import CartItem
from carts.views import cart_id
from category.models import Category , CategoryRequest
from orders.models import OrderProduct
from .models import Product,ReviewRating,ProductGallery,Variation
from .forms import ReviewForm,ProductForm
from django.utils.text import slugify
from uuid import uuid4

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
        product=single_product.id,
        status=True
    )

    product_gallery=ProductGallery.objects.filter(
        product_id=single_product.id
    )

    context={
        'single_product':single_product,
        'in_cart':in_cart,
        'orderproduct':orderproduct,
        'reviews':reviews,
        'product_gallery':product_gallery,
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


@login_required(login_url='login')
def vendor_required(request):
    if not request.user.is_vendor:
        messages.error(
            request,
            'You are not registered as a vendor.'
        )
        return False

    try:
        vendor_profile=request.user.vendorprofile
    except request.user.vendorprofile.RelatedObjectDoesNotExist:
        messages.error(
            request,
            'Vendor profile not found.'
        )
        return False

    if not vendor_profile.is_approved:
        messages.warning(
            request,
            'Your vendor account is waiting for admin approval.'
        )
        return False

    return True


@login_required(login_url='login')
def vendor_products(request):
    if not vendor_required(request):
        return redirect('dashboard')

    products=Product.objects.filter(
        vendor=request.user
    ).order_by('-created_date')

    return render(
        request,
        'store/vendor_products.html',
        {'products':products}
    )


@login_required(login_url='login')
def vendor_product_add(request):
    if not vendor_required(request):
        return redirect('dashboard')

    if request.method=='POST':
        form=ProductForm(request.POST,request.FILES)

        if form.is_valid():
            product=form.save(commit=False)
            product.vendor=request.user

            slug=slugify(product.product_name)

            if Product.objects.filter(slug=slug).exists():
                slug=slug+'-'+uuid4().hex[:6]

            product.slug=slug
            product.save()

            colors=request.POST.get('colors','')
            sizes=request.POST.get('sizes','')

            for color in colors.split(','):
                color=color.strip()

                if color:
                    Variation.objects.create(
                        product=product,
                        variation_category='color',
                        variation_value=color
                    )

            for size in sizes.split(','):
                size=size.strip()

                if size:
                    Variation.objects.create(
                        product=product,
                        variation_category='size',
                        variation_value=size
                    )

            gallery_images=request.FILES.getlist('gallery_images')

            for image in gallery_images:
                ProductGallery.objects.create(
                    product=product,
                    image=image
                )

            messages.success(
                request,
                'Product added successfully.'
            )

            return redirect('vendor_products')

    else:
        form=ProductForm()

    return render(
        request,
        'store/vendor_product_form.html',
        {
            'form':form,
            'title':'Add Product'
        }
    )


@login_required(login_url='login')
def vendor_product_edit(request,product_id):
    if not vendor_required(request):
        return redirect('dashboard')

    product=get_object_or_404(
        Product,
        id=product_id,
        vendor=request.user
    )

    if request.method=='POST':
        form=ProductForm(
            request.POST,
            request.FILES,
            instance=product
        )

        if form.is_valid():
            product=form.save(commit=False)
            product.vendor=request.user
            product.save()

            Variation.objects.filter(
                product=product
            ).delete()

            colors=request.POST.get('colors','')
            sizes=request.POST.get('sizes','')

            for color in colors.split(','):
                color=color.strip()

                if color:
                    Variation.objects.create(
                        product=product,
                        variation_category='color',
                        variation_value=color
                    )

            for size in sizes.split(','):
                size=size.strip()

                if size:
                    Variation.objects.create(
                        product=product,
                        variation_category='size',
                        variation_value=size
                    )

            gallery_images=request.FILES.getlist('gallery_images')

            for image in gallery_images:
                ProductGallery.objects.create(
                    product=product,
                    image=image
                )

            messages.success(
                request,
                'Product updated successfully.'
            )

            return redirect('vendor_products')

    else:
        form=ProductForm(instance=product)

    colors=Variation.objects.filter(
        product=product,
        variation_category='color',
        is_active=True
    ).values_list(
        'variation_value',
        flat=True
    )

    sizes=Variation.objects.filter(
        product=product,
        variation_category='size',
        is_active=True
    ).values_list(
        'variation_value',
        flat=True
    )

    gallery=ProductGallery.objects.filter(
        product=product
    )

    return render(
        request,
        'store/vendor_product_form.html',
        {
            'form':form,
            'title':'Edit Product',
            'product':product,
            'colors':', '.join(colors),
            'sizes':', '.join(sizes),
            'gallery':gallery
        }
    )


@login_required(login_url='login')
def vendor_product_delete(request,product_id):
    if not vendor_required(request):
        return redirect('dashboard')

    product=get_object_or_404(
        Product,
        id=product_id,
        vendor=request.user
    )

    if request.method=='POST':
        product.delete()

        messages.success(
            request,
            'Product deleted successfully.'
        )

        return redirect('vendor_products')

    return render(
        request,
        'store/vendor_product_delete.html',
        {'product':product}
    )

@login_required(login_url='login')
def request_category(request):
    if not request.user.is_vendor:
        messages.error(request,'Only vendors can request new categories.')
        return redirect('dashboard')

    if request.method=='POST':
        category_name=request.POST.get('category_name')
        description=request.POST.get('description','')

        if not category_name:
            messages.error(request,'Category name is required.')
            return redirect('request_category')

        existing=CategoryRequest.objects.filter(
            vendor=request.user,
            category_name__iexact=category_name,
            status='pending'
        ).exists()

        if existing:
            messages.warning(request,'You already have a pending request for this category.')
            return redirect('request_category')

        CategoryRequest.objects.create(
            vendor=request.user,
            category_name=category_name,
            description=description
        )

        messages.success(
            request,
            'Category request submitted. Admin approval is required.'
        )

        return redirect('vendor_orders')

    return render(request,'store/request_category.html')