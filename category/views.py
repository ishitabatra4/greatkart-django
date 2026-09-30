from django.shortcuts import render,redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import CategoryRequest

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