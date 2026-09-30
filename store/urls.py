from django.urls import path
from . import views

urlpatterns = [
    path('', views.store, name='store'),
    path('category/<slug:category_slug>/', views.store, name='products_by_category'),
    path('category/<slug:category_slug>/<slug:product_slug>/', views.product_detail, name='product_detail'),
    path('search/', views.search, name='search'),
    path('submit_review/<int:product_id>/', views.submit_review, name='submit_review'),

    path('vendor/products/', views.vendor_products, name='vendor_products'),
    path('vendor/products/add/', views.vendor_product_add, name='vendor_product_add'),
    path('vendor/products/edit/<int:product_id>/', views.vendor_product_edit, name='vendor_product_edit'),
    path('vendor/products/delete/<int:product_id>/', views.vendor_product_delete, name='vendor_product_delete'),

    path('vendor/request-category/', views.request_category, name='request_category'),
]