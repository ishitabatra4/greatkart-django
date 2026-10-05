from django.shortcuts import render,redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from category.models import Category, CategoryRequest
from accounts.permissions import IsApprovedVendor
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from accounts.permissions import IsApprovedVendor

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


@api_view(['POST'])
@permission_classes([IsApprovedVendor])
def api_request_category(request):

    category_name = request.data.get('category_name')
    description = request.data.get('description', '')

    if not category_name:
        return Response(
            {
                'message': 'Category name is required.'
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    category_name = category_name.strip()

    existing = CategoryRequest.objects.filter(
        vendor=request.user,
        category_name__iexact=category_name,
        status='pending'
    ).exists()

    if existing:
        return Response(
            {
                'message': 'You already have a pending request for this category.'
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    category_request = CategoryRequest.objects.create(
        vendor=request.user,
        category_name=category_name,
        description=description
    )

    return Response(
        {
            'message': 'Category request submitted successfully.',
            'category_request_id': category_request.id,
            'category_name': category_request.category_name,
            'description': category_request.description,
            'status': category_request.status
        },
        status=status.HTTP_201_CREATED
    )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_categories(request):

    categories = Category.objects.all().order_by('category_name')

    data = []

    for category in categories:
        data.append({
            'id': category.id,
            'name': category.category_name,
            'slug': category.slug,
        })

    return Response(
        {
            'count': len(data),
            'categories': data
        },
        status=status.HTTP_200_OK
    )