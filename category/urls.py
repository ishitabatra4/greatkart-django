from django.urls import path
from . import views

urlpatterns=[
    path('request-category/',views.request_category,name='request_category'),
    path('api/vendor/request-category/',views.api_request_category,name='api_request_category'),
    path('api/categories/',views.api_categories,name='api_categories'),
    path('api/admin/categories/',views.api_admin_categories,name='api_admin_categories'),
    path('api/admin/categories/<int:category_id>/',views.api_admin_category_detail,name='api_admin_category_detail'),
    path('api/admin/category-requests/',views.api_admin_category_requests,name='api_admin_category_requests'),
    path('api/admin/category-requests/<int:request_id>/approve/',views.api_admin_category_request_approve,name='api_admin_category_request_approve'),
    path('api/admin/category-requests/<int:request_id>/reject/',views.api_admin_category_request_reject,name='api_admin_category_request_reject'),
]