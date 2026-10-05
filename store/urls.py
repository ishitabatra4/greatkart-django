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

    path('api/products/', views.api_products, name='api_products'),
    path('api/products/<int:product_id>/', views.api_product_detail, name='api_product_detail'),

    path('api/vendor/products/', views.api_vendor_products, name='api_vendor_products'),
    path('api/vendor/products/add/', views.api_vendor_product_add, name='api_vendor_product_add'),
    path('api/vendor/products/<int:product_id>/', views.api_vendor_product_edit, name='api_vendor_product_edit'),
    path('api/vendor/products/<int:product_id>/delete/', views.api_vendor_product_delete, name='api_vendor_product_delete'),
    path('api/products/<int:product_id>/variations/',views.api_product_variations,name='api_product_variations'),
    path('api/products/<int:product_id>/',views.api_product_detail,name='api_product_detail'),
    path('api/category/<slug:category_slug>/',views.api_category_products,name='api_category_products'),
    path('api/products/<int:product_id>/reviews/',views.api_product_reviews,name='api_product_reviews'),
    path('api/search/',views.api_search_products,name='api_search_products'),
]