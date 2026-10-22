from django.shortcuts import render,redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from category.models import Category, CategoryRequest
from accounts.permissions import IsApprovedVendor
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated,IsAdminUser
from django.utils.text import slugify
from rest_framework.permissions import AllowAny

from accounts.permissions import IsApprovedVendor


@login_required(login_url='login')
def request_category(request):
    if not request.user.is_vendor:
        messages.error(request, 'Only vendors can create categories.')
        return redirect('dashboard')

    if request.method == 'POST':
        category_name = request.POST.get('category_name', '').strip()
        description = request.POST.get('description', '').strip()

        if not category_name:
            messages.error(request, 'Category name is required.')
            return redirect('request_category')

        if Category.objects.filter(
            category_name__iexact=category_name
        ).exists():
            messages.warning(request, 'This category already exists.')
            return redirect('request_category')

        slug = slugify(category_name)
        original_slug = slug
        counter = 1

        while Category.objects.filter(slug=slug).exists():
            slug = f'{original_slug}-{counter}'
            counter += 1

        Category.objects.create(
            category_name=category_name,
            slug=slug,
            description=description,
            is_approved=True
        )

        messages.success(
            request,
            f'Category "{category_name}" created successfully!'
        )
        return redirect('vendor_orders')

    return render(request, 'store/request_category.html')



@api_view(['POST'])
@permission_classes([IsApprovedVendor])
def api_request_category(request):
    category_name = request.data.get('category_name', '')
    description = request.data.get('description', '')

    if not isinstance(category_name, str):
        return Response(
            {'message': 'Category name must be text.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    category_name = category_name.strip()

    if not category_name:
        return Response(
            {'message': 'Category name is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if Category.objects.filter(
        category_name__iexact=category_name
    ).exists():
        return Response(
            {'message': 'Category already exists.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    slug = slugify(category_name)
    original_slug = slug
    counter = 1

    while Category.objects.filter(slug=slug).exists():
        slug = f'{original_slug}-{counter}'
        counter += 1

    category = Category.objects.create(
        category_name=category_name,
        slug=slug,
        description=description,
        is_approved=True
    )

    return Response(
        {
            'message': 'Category created successfully.',
            'category': {
                'id': category.id,
                'category_name': category.category_name,
                'slug': category.slug,
                'description': category.description,
                'is_approved': category.is_approved,
            }
        },
        status=status.HTTP_201_CREATED
    )


@api_view(['GET'])
@permission_classes([AllowAny])
def api_categories(request):
    categories = Category.objects.filter(
        is_approved=True
    ).order_by('category_name')

    data = [
        {
            'id': category.id,
            'name': category.category_name,
            'slug': category.slug,
            'url': category.get_url(),
        }
        for category in categories
    ]

    return Response(
        {
            'count': len(data),
            'categories': data,
        },
        status=status.HTTP_200_OK
    )

@api_view(['GET', 'POST'])
@permission_classes([IsAdminUser])
def api_admin_categories(request):

    # GET ALL CATEGORIES
    if request.method == 'GET':

        categories = Category.objects.all().order_by('category_name')

        data = []

        for category in categories:
            data.append({
                'id': category.id,
                'category_name': category.category_name,
                'slug': category.slug,
                'description': category.description,
                'cat_image': (
                    request.build_absolute_uri(category.cat_image.url)
                    if category.cat_image
                    else None
                ),
                'is_approved': category.is_approved,
            })

        return Response({
            'count': len(data),
            'categories': data
        })

    # POST CREATE CATEGORY

    category_name = request.data.get('category_name')
    description = request.data.get('description', '')
    cat_image = request.FILES.get('cat_image')

    if not category_name:
        return Response(
            {'message': 'Category name is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    category_name = category_name.strip()

    if Category.objects.filter(
        category_name__iexact=category_name
    ).exists():
        return Response(
            {'message': 'Category already exists.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    slug = slugify(category_name)

    # Make slug unique
    original_slug = slug
    counter = 1

    while Category.objects.filter(slug=slug).exists():
        slug = f'{original_slug}-{counter}'
        counter += 1

    category = Category.objects.create(
        category_name=category_name,
        slug=slug,
        description=description,
        cat_image=cat_image,
        is_approved=True
    )

    return Response(
        {
            'message': 'Category created successfully.',
            'category': {
                'id': category.id,
                'category_name': category.category_name,
                'slug': category.slug,
                'description': category.description,
                'cat_image': (
                    request.build_absolute_uri(category.cat_image.url)
                    if category.cat_image
                    else None
                ),
                'is_approved': category.is_approved,
            }
        },
        status=status.HTTP_201_CREATED
    )

@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAdminUser])
def api_admin_category_detail(request, category_id):

    try:
        category = Category.objects.get(id=category_id)

    except Category.DoesNotExist:
        return Response(
            {'message': 'Category not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    # GET
    if request.method == 'GET':

        return Response({
            'id': category.id,
            'category_name': category.category_name,
            'slug': category.slug,
            'description': category.description,
            'cat_image': (
                request.build_absolute_uri(category.cat_image.url)
                if category.cat_image
                else None
            ),
            'is_approved': category.is_approved,
        })

    # PATCH
    if request.method == 'PATCH':

        category_name = request.data.get('category_name')
        description = request.data.get('description')
        cat_image = request.FILES.get('cat_image')

        if category_name is not None:

            category_name = category_name.strip()

            if not category_name:
                return Response(
                    {'message': 'Category name cannot be empty.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            existing = Category.objects.filter(
                category_name__iexact=category_name
            ).exclude(id=category.id).exists()

            if existing:
                return Response(
                    {'message': 'Category already exists.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            category.category_name = category_name

            slug = slugify(category_name)

            original_slug = slug
            counter = 1

            while Category.objects.filter(
                slug=slug
            ).exclude(id=category.id).exists():

                slug = f'{original_slug}-{counter}'
                counter += 1

            category.slug = slug

        if description is not None:
            category.description = description

        if cat_image:
            category.cat_image = cat_image

        if 'is_approved' in request.data:
            category.is_approved = request.data.get('is_approved')

        category.save()

        return Response({
            'message': 'Category updated successfully.',
            'category': {
                'id': category.id,
                'category_name': category.category_name,
                'slug': category.slug,
                'description': category.description,
                'cat_image': (
                    request.build_absolute_uri(category.cat_image.url)
                    if category.cat_image
                    else None
                ),
                'is_approved': category.is_approved,
            }
        })

    # DELETE
    if request.method == 'DELETE':

        category_name = category.category_name

        category.delete()

        return Response({
            'message': 'Category deleted successfully.',
            'category_name': category_name
        })

@api_view(['GET'])
@permission_classes([IsAdminUser])
def api_admin_category_requests(request):

    requests = CategoryRequest.objects.filter(
        status='pending'
    ).select_related(
        'vendor'
    ).order_by('-created_at')

    data = []

    for category_request in requests:

        data.append({
            'id': category_request.id,

            'vendor': {
                'id': category_request.vendor.id,
                'name': (
                    f'{category_request.vendor.first_name} '
                    f'{category_request.vendor.last_name}'
                ).strip(),
                'username': category_request.vendor.username,
                'email': category_request.vendor.email,
            },

            'category_name': category_request.category_name,
            'description': category_request.description,
            'status': category_request.status,
            'created_at': category_request.created_at,
        })

    return Response({
        'count': len(data),
        'requests': data
    })    

@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def api_admin_category_request_approve(request, request_id):

    try:
        category_request = CategoryRequest.objects.select_related(
            'vendor'
        ).get(id=request_id)

    except CategoryRequest.DoesNotExist:
        return Response(
            {'message': 'Category request not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    if category_request.status != 'pending':
        return Response(
            {
                'message': 'Only pending category requests can be approved.',
                'current_status': category_request.status
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    category_name = category_request.category_name.strip()

    # Check if category already exists
    if Category.objects.filter(
        category_name__iexact=category_name
    ).exists():

        return Response(
            {
                'message': 'A category with this name already exists.'
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    # Generate unique slug
    slug = slugify(category_name)

    original_slug = slug
    counter = 1

    while Category.objects.filter(slug=slug).exists():
        slug = f'{original_slug}-{counter}'
        counter += 1

    category = Category.objects.create(
        category_name=category_name,
        slug=slug,
        description=category_request.description,
        is_approved=True
    )

    category_request.status = 'approved'
    category_request.save(update_fields=['status'])

    return Response({
        'message': 'Category request approved successfully.',

        'category_request': {
            'id': category_request.id,
            'status': category_request.status,
        },

        'category': {
            'id': category.id,
            'category_name': category.category_name,
            'slug': category.slug,
            'description': category.description,
            'is_approved': category.is_approved,
        }
    })

@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def api_admin_category_request_reject(request, request_id):

    try:
        category_request = CategoryRequest.objects.get(
            id=request_id
        )

    except CategoryRequest.DoesNotExist:
        return Response(
            {'message': 'Category request not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    if category_request.status != 'pending':
        return Response(
            {
                'message': 'Only pending category requests can be rejected.',
                'current_status': category_request.status
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    category_request.status = 'rejected'
    category_request.save(update_fields=['status'])

    return Response({
        'message': 'Category request rejected successfully.',
        'category_request': {
            'id': category_request.id,
            'category_name': category_request.category_name,
            'status': category_request.status,
        }
    })