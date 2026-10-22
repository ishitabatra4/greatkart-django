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
from rest_framework.decorators import api_view,permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser,FormParser
from accounts.permissions import IsApprovedVendor,IsAdminUser
from accounts.models import VendorProfile
from accounts.models import Account
from .serializers import ProductSerializer
from rest_framework.pagination import PageNumberPagination

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
        vendor_profile=VendorProfile.objects.get(
            user=request.user
        )

    except VendorProfile.DoesNotExist:
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

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_products(request):

    products = Product.objects.filter(
        is_available=True,
        stock__gt=0
    )

    # 🔎 Search by product name
    search = request.GET.get('search')
    if search:
        products = products.filter(
            product_name__icontains=search
        )

    # 🗂️ Category filter: supports category ID and category slug
    category_slug = request.GET.get('category_slug')
    category_id = request.GET.get('category')

    if category_slug:
        products = products.filter(
            category__slug=category_slug
        )
    elif category_id:
        products = products.filter(
            category__id=category_id
        )

    # 🏷️ Brand filter
    brand = request.GET.get('brand')
    if brand:
        products = products.filter(
            brand__iexact=brand
        )

    # 💰 Minimum price
    min_price = request.GET.get('min_price')
    if min_price:
        products = products.filter(
            price__gte=min_price
        )

    # 💰 Maximum price
    max_price = request.GET.get('max_price')
    if max_price:
        products = products.filter(
            price__lte=max_price
        )

    # ↕️ Sorting
    sort = request.GET.get('sort')

    if sort == 'price_asc':
        products = products.order_by('price')
    elif sort == 'price_desc':
        products = products.order_by('-price')
    else:
        products = products.order_by('-created_date')

    # 📄 Pagination — filters are applied before pagination
    paginator = PageNumberPagination()
    paginator.page_size = 6

    result_page = paginator.paginate_queryset(
        products,
        request
    )

    serializer = ProductSerializer(
        result_page,
        many=True,
        context={'request': request}
    )

    return paginator.get_paginated_response(
        serializer.data
    )

@api_view(['GET'])
@permission_classes([IsApprovedVendor])
def api_vendor_products(request):

    products=Product.objects.filter(
        vendor=request.user
    ).order_by('-created_date')

    serializer=ProductSerializer(
        products,
        many=True,
        context={'request':request}
    )

    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsApprovedVendor])
def api_vendor_product_add(request):

    form=ProductForm(
        request.data,
        request.FILES
    )

    if not form.is_valid():
        return Response(
            form.errors,
            status=status.HTTP_400_BAD_REQUEST
        )

    product=form.save(commit=False)
    product.vendor=request.user
    if product.stock > 0:
        product.is_available = True
    else:
        product.is_available = False

    slug=slugify(product.product_name)

    if Product.objects.filter(slug=slug).exists():
        slug=slug+'-'+uuid4().hex[:6]

    product.slug=slug
    product.save()

    colors=request.data.get('colors','')
    sizes=request.data.get('sizes','')

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

    serializer=ProductSerializer(
        product,
        context={'request':request}
    )

    return Response(
        {
            'message':'Product added successfully.',
            'product':serializer.data
        },
        status=status.HTTP_201_CREATED
    )


@api_view(['PUT','PATCH'])
@permission_classes([IsApprovedVendor])
def api_vendor_product_edit(request,product_id):

    try:
        product=Product.objects.get(
            id=product_id,
            vendor=request.user
        )
    except Product.DoesNotExist:
        return Response(
            {
                'message':'Product not found or you do not own this product.'
            },
            status=status.HTTP_404_NOT_FOUND
        )

    form=ProductForm(
        request.data,
        request.FILES,
        instance=product
    )

    if not form.is_valid():
        return Response(
            form.errors,
            status=status.HTTP_400_BAD_REQUEST
        )

    product=form.save(commit=False)
    product.vendor=request.user
    if product.stock > 0:
        product.is_available = True
    else:
        product.is_available = False
    product.save()

    Variation.objects.filter(
        product=product
    ).delete()

    colors=request.data.get('colors','')
    sizes=request.data.get('sizes','')

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

    serializer=ProductSerializer(
        product,
        context={'request':request}
    )

    return Response(
        {
            'message':'Product updated successfully.',
            'product':serializer.data
        }
    )


@api_view(['DELETE'])
@permission_classes([IsApprovedVendor])
def api_vendor_product_delete(request,product_id):

    try:
        product=Product.objects.get(
            id=product_id,
            vendor=request.user
        )
    except Product.DoesNotExist:
        return Response(
            {
                'message':'Product not found or you do not own this product.'
            },
            status=status.HTTP_404_NOT_FOUND
        )

    product.delete()

    return Response(
        {
            'message':'Product deleted successfully.'
        },
        status=status.HTTP_200_OK
    )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_product_variations(request, product_id):

    try:
        product = Product.objects.get(
            id=product_id,
            is_available=True
        )
    except Product.DoesNotExist:
        return Response(
            {'message': 'Product not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    variations = Variation.objects.filter(
        product=product,
        is_active=True
    ).order_by('variation_category', 'id')

    data = {
        'product_id': product.id,
        'product_name': product.product_name,
        'variations': {
            'color': [],
            'size': []
        }
    }

    for variation in variations:

        category = variation.variation_category.lower()

        if category in data['variations']:
            data['variations'][category].append({
                'id': variation.id,
                'value': variation.variation_value
            })

    return Response(data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_product_detail(request, product_id):

    try:
        product = Product.objects.get(
            id=product_id,
            is_available=True
        )
    except Product.DoesNotExist:
        return Response(
            {
                'message': 'Product not found.'
            },
            status=status.HTTP_404_NOT_FOUND
        )

    variations = Variation.objects.filter(
        product=product,
        is_active=True
    )

    colors = []
    sizes = []

    for variation in variations:

        if variation.variation_category == 'color':
            colors.append({
                'id': variation.id,
                'value': variation.variation_value
            })

        elif variation.variation_category == 'size':
            sizes.append({
                'id': variation.id,
                'value': variation.variation_value
            })

    data = {
        'id': product.id,
        'product_name': product.product_name,
        'slug': product.slug,
        'description': product.description,
        'price': float(product.price),
        'stock': product.stock,
        'is_available': product.is_available,

        'image': request.build_absolute_uri(product.images.url) if product.images else None,

        'gallery': [
            request.build_absolute_uri(item.image.url)
            for item in ProductGallery.objects.filter(product=product)
            if item.image
        ],

        'category': {
            'id': product.category.id,
            'name': product.category.category_name,
        },

        'variations': {
            'colors': colors,
            'sizes': sizes,
        }
    }

    return Response(data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_category_products(request, category_slug):

    try:
        category = Category.objects.get(
            slug=category_slug
        )

    except Category.DoesNotExist:
        return Response(
            {
                'message': 'Category not found.'
            },
            status=status.HTTP_404_NOT_FOUND
        )

    products = Product.objects.filter(
        category=category,
        is_available=True,
        stock__gt=0
    ).order_by('id')

    serializer = ProductSerializer(
        products,
        many=True,
        context={'request': request}
    )

    return Response(
        {
            'category': {
                'id': category.id,
                'name': category.category_name,
                'slug': category.slug
            },
            'count': products.count(),
            'products': serializer.data
        },
        status=status.HTTP_200_OK
    )
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_search_products(request):

    keyword = request.GET.get('keyword', '').strip()

    if not keyword:
        return Response(
            {
                'message': 'Search keyword is required.',
                'count': 0,
                'products': []
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    products = Product.objects.filter(
        is_available=True,
        stock__gt=0
    ).filter(
        Q(description__icontains=keyword) |
        Q(product_name__icontains=keyword) |
        Q(brand__icontains=keyword)
    ).order_by('-created_date')

    serializer = ProductSerializer(
        products,
        many=True,
        context={'request': request}
    )

    return Response(
        {
            'keyword': keyword,
            'count': products.count(),
            'products': serializer.data
        },
        status=status.HTTP_200_OK
    )

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def api_product_reviews(request, product_id):

    try:
        product = Product.objects.get(
            id=product_id,
            is_available=True
        )

    except Product.DoesNotExist:
        return Response(
            {
                'message': 'Product not found.'
            },
            status=status.HTTP_404_NOT_FOUND
        )

    # GET REVIEWS
    if request.method == 'GET':

        reviews = ReviewRating.objects.filter(
            product=product,
            status=True
        ).select_related('user').order_by('-updated_at')

        total_reviews = reviews.count()

        if total_reviews > 0:
            average_rating = sum(
                review.rating for review in reviews
            ) / total_reviews
        else:
            average_rating = 0

        review_data = []

        for review in reviews:

            review_data.append(
                {
                    'id': review.id,
                    'user_id': review.user.id,
                    'user_name': (
                        review.user.first_name +
                        ' ' +
                        review.user.last_name
                    ).strip(),
                    'subject': review.subject,
                    'rating': review.rating,
                    'review': review.review,
                    'created_at': review.created_at,
                    'updated_at': review.updated_at
                }
            )

        return Response(
            {
                'product_id': product.id,
                'product_name': product.product_name,
                'average_rating': round(
                    average_rating,
                    1
                ),
                'total_reviews': total_reviews,
                'reviews': review_data
            },
            status=status.HTTP_200_OK
        )

    # POST REVIEW

    subject = request.data.get('subject')
    rating = request.data.get('rating')
    review_text = request.data.get('review')

    if not subject:
        return Response(
            {
                'message': 'Subject is required.'
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    if not rating:
        return Response(
            {
                'message': 'Rating is required.'
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    if not review_text:
        return Response(
            {
                'message': 'Review is required.'
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        rating = float(rating)
    except (TypeError, ValueError):

        return Response(
            {
                'message': 'Rating must be a number.'
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    if rating < 1 or rating > 5:

        return Response(
            {
                'message': 'Rating must be between 1 and 5.'
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    review_obj, created = ReviewRating.objects.update_or_create(
        user=request.user,
        product=product,
        defaults={
            'subject': subject,
            'rating': rating,
            'review': review_text,
            'ip': request.META.get('REMOTE_ADDR'),
            'status': True
        }
    )

    return Response(
        {
            'message': (
                'Review submitted successfully.'
                if created
                else
                'Review updated successfully.'
            ),
            'review_id': review_obj.id,
            'product_id': product.id,
            'subject': review_obj.subject,
            'rating': review_obj.rating,
            'review': review_obj.review,
            'status': review_obj.status
        },
        status=(
            status.HTTP_201_CREATED
            if created
            else status.HTTP_200_OK
        )
    )

@api_view(['GET', 'POST'])
@permission_classes([IsAdminUser])
def api_admin_products(request):

    # =====================================================
    # GET ALL PRODUCTS
    # =====================================================

    if request.method == 'GET':

        products = Product.objects.select_related(
            'vendor',
            'category'
        ).prefetch_related(
            'variation_set',
            'productgallery_set'
        ).order_by('-created_date')

        data = []

        for product in products:

            colors = []
            sizes = []

            for variation in product.variation_set.all():

                variation_data = {
                    'id': variation.id,
                    'value': variation.variation_value,
                    'is_active': variation.is_active
                }

                if variation.variation_category == 'color':
                    colors.append(variation_data)

                elif variation.variation_category == 'size':
                    sizes.append(variation_data)

            gallery = []

            for image in product.productgallery_set.all():

                gallery.append({
                    'id': image.id,
                    'image': request.build_absolute_uri(
                        image.image.url
                    ) if image.image else None
                })

            data.append({

                'id': product.id,

                'product_name': product.product_name,
                'brand': product.brand,
                'slug': product.slug,
                'description': product.description,

                'price': product.price,
                'stock': product.stock,
                'is_available': product.is_available,

                'category': {
                    'id': product.category.id,
                    'name': product.category.category_name,
                    'slug': product.category.slug
                },

                'vendor': (
                    {
                        'id': product.vendor.id,
                        'first_name': product.vendor.first_name,
                        'last_name': product.vendor.last_name,
                        'email': product.vendor.email
                    }
                    if product.vendor
                    else None
                ),

                'main_image': (
                    request.build_absolute_uri(
                        product.images.url
                    )
                    if product.images
                    else None
                ),

                'variations': {
                    'colors': colors,
                    'sizes': sizes
                },

                'gallery': gallery,

                'created_date': product.created_date,
                'modified_date': product.modified_date
            })

        return Response({
            'count': len(data),
            'products': data
        })


    # =====================================================
    # POST - CREATE PRODUCT
    # =====================================================

    product_name = request.data.get('product_name')
    brand = request.data.get('brand', '')
    description = request.data.get('description', '')
    price = request.data.get('price')
    stock = request.data.get('stock')
    category_id = request.data.get('category_id')
    vendor_id = request.data.get('vendor_id')

    # -----------------------------------------------------
    # REQUIRED FIELDS
    # -----------------------------------------------------

    if not product_name:
        return Response(
            {'message': 'Product name is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if price is None:
        return Response(
            {'message': 'Price is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if stock is None:
        return Response(
            {'message': 'Stock is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if not category_id:
        return Response(
            {'message': 'Category is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if not vendor_id:
        return Response(
            {'message': 'Vendor is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # -----------------------------------------------------
    # VALIDATE PRICE AND STOCK
    # -----------------------------------------------------

    try:
        price = int(price)
        stock = int(stock)

    except (TypeError, ValueError):

        return Response(
            {'message': 'Price and stock must be valid numbers.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if price < 0:
        return Response(
            {'message': 'Price cannot be negative.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if stock < 0:
        return Response(
            {'message': 'Stock cannot be negative.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # -----------------------------------------------------
    # CATEGORY
    # -----------------------------------------------------

    try:
        category = Category.objects.get(
            id=category_id
        )

    except Category.DoesNotExist:

        return Response(
            {'message': 'Category not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    # -----------------------------------------------------
    # VENDOR
    # -----------------------------------------------------

    try:
        vendor = Account.objects.get(
            id=vendor_id,
            is_vendor=True
        )

    except Account.DoesNotExist:

        return Response(
            {'message': 'Vendor not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    # -----------------------------------------------------
    # VENDOR MUST BE APPROVED
    # -----------------------------------------------------

    try:

        if not vendor.vendorprofile.is_approved:

            return Response(
                {'message': 'Vendor is not approved.'},
                status=status.HTTP_400_BAD_REQUEST
            )

    except VendorProfile.DoesNotExist:

        return Response(
            {'message': 'Vendor profile not found.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # -----------------------------------------------------
    # MAIN IMAGE
    # -----------------------------------------------------

    main_image = request.FILES.get('images')

    if not main_image:

        return Response(
            {'message': 'Product image is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # -----------------------------------------------------
    # GENERATE UNIQUE SLUG
    # -----------------------------------------------------

    slug = slugify(product_name)

    if Product.objects.filter(slug=slug).exists():

        slug = slug + '-' + uuid4().hex[:6]

    # -----------------------------------------------------
    # CREATE PRODUCT
    # -----------------------------------------------------

    product = Product.objects.create(

        vendor=vendor,

        product_name=product_name,

        brand=brand,

        slug=slug,

        description=description,

        price=price,

        images=main_image,

        stock=stock,

        is_available=stock > 0,

        category=category
    )

    # =====================================================
    # VARIATIONS
    # =====================================================

    colors = request.data.get('colors', '')
    sizes = request.data.get('sizes', '')

    # Colors
    for color in colors.split(','):

        color = color.strip()

        if color:

            Variation.objects.create(
                product=product,
                variation_category='color',
                variation_value=color,
                is_active=True
            )

    # Sizes
    for size in sizes.split(','):

        size = size.strip()

        if size:

            Variation.objects.create(
                product=product,
                variation_category='size',
                variation_value=size,
                is_active=True
            )

    # =====================================================
    # GALLERY IMAGES
    # =====================================================

    gallery_images = request.FILES.getlist(
        'gallery_images'
    )

    for image in gallery_images:

        ProductGallery.objects.create(
            product=product,
            image=image
        )

    # =====================================================
    # RESPONSE
    # =====================================================

    return Response(
        {
            'message': 'Product created successfully.',
            'product_id': product.id
        },
        status=status.HTTP_201_CREATED
    )

@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAdminUser])
def api_admin_product_detail(request, product_id):

    try:

        product = Product.objects.select_related(
            'vendor',
            'category'
        ).get(
            id=product_id
        )

    except Product.DoesNotExist:

        return Response(
            {'message': 'Product not found.'},
            status=status.HTTP_404_NOT_FOUND
        )


    # =====================================================
    # GET DETAIL
    # =====================================================

    if request.method == 'GET':

        variations = Variation.objects.filter(
            product=product
        )

        colors = []
        sizes = []

        for variation in variations:

            data = {
                'id': variation.id,
                'value': variation.variation_value,
                'is_active': variation.is_active
            }

            if variation.variation_category == 'color':
                colors.append(data)

            elif variation.variation_category == 'size':
                sizes.append(data)

        gallery = []

        for image in ProductGallery.objects.filter(
            product=product
        ):

            gallery.append({
                'id': image.id,
                'image': request.build_absolute_uri(
                    image.image.url
                ) if image.image else None
            })

        return Response({

            'id': product.id,

            'product_name': product.product_name,
            'brand': product.brand,
            'slug': product.slug,
            'description': product.description,

            'price': product.price,
            'stock': product.stock,
            'is_available': product.is_available,

            'category': {
                'id': product.category.id,
                'name': product.category.category_name,
                'slug': product.category.slug
            },

            'vendor': (
                {
                    'id': product.vendor.id,
                    'first_name': product.vendor.first_name,
                    'last_name': product.vendor.last_name,
                    'email': product.vendor.email
                }
                if product.vendor
                else None
            ),

            'main_image': (
                request.build_absolute_uri(
                    product.images.url
                )
                if product.images
                else None
            ),

            'variations': {
                'colors': colors,
                'sizes': sizes
            },

            'gallery': gallery,

            'created_date': product.created_date,
            'modified_date': product.modified_date
        })


    # =====================================================
    # PATCH
    # =====================================================

    if request.method == 'PATCH':

        if 'product_name' in request.data:

            product.product_name = request.data[
                'product_name'
            ]

        if 'brand' in request.data:

            product.brand = request.data[
                'brand'
            ]

        if 'description' in request.data:

            product.description = request.data[
                'description'
            ]

        if 'price' in request.data:

            try:
                product.price = int(
                    request.data['price']
                )

            except (TypeError, ValueError):

                return Response(
                    {'message': 'Invalid price.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        if 'stock' in request.data:

            try:
                product.stock = int(
                    request.data['stock']
                )

            except (TypeError, ValueError):

                return Response(
                    {'message': 'Invalid stock.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        if 'is_available' in request.data:

            product.is_available = request.data[
                'is_available'
            ]

        else:

            product.is_available = product.stock > 0

        # Category

        if 'category_id' in request.data:

            try:

                category = Category.objects.get(
                    id=request.data['category_id']
                )

                product.category = category

            except Category.DoesNotExist:

                return Response(
                    {'message': 'Category not found.'},
                    status=status.HTTP_404_NOT_FOUND
                )

        # Vendor

        if 'vendor_id' in request.data:

            try:

                vendor = Account.objects.get(
                    id=request.data['vendor_id'],
                    is_vendor=True
                )

                if not vendor.vendorprofile.is_approved:

                    return Response(
                        {
                            'message':
                            'Vendor is not approved.'
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )

                product.vendor = vendor

            except Account.DoesNotExist:

                return Response(
                    {'message': 'Vendor not found.'},
                    status=status.HTTP_404_NOT_FOUND
                )

            except VendorProfile.DoesNotExist:

                return Response(
                    {
                        'message':
                        'Vendor profile not found.'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Main image

        if 'images' in request.FILES:

            product.images = request.FILES[
                'images'
            ]

        product.save()

        # =================================================
        # REPLACE VARIATIONS IF SENT
        # =================================================

        if (
            'colors' in request.data or
            'sizes' in request.data
        ):

            Variation.objects.filter(
                product=product
            ).delete()

            colors = request.data.get(
                'colors',
                ''
            )

            sizes = request.data.get(
                'sizes',
                ''
            )

            for color in colors.split(','):

                color = color.strip()

                if color:

                    Variation.objects.create(
                        product=product,
                        variation_category='color',
                        variation_value=color
                    )

            for size in sizes.split(','):

                size = size.strip()

                if size:

                    Variation.objects.create(
                        product=product,
                        variation_category='size',
                        variation_value=size
                    )

        # =================================================
        # ADD NEW GALLERY IMAGES
        # =================================================

        gallery_images = request.FILES.getlist(
            'gallery_images'
        )

        for image in gallery_images:

            ProductGallery.objects.create(
                product=product,
                image=image
            )

        return Response({

            'message':
            'Product updated successfully.',

            'product_id':
            product.id
        })


    # =====================================================
    # DELETE
    # =====================================================

    if request.method == 'DELETE':

        product.delete()

        return Response({

            'message':
            'Product deleted successfully.'
        })