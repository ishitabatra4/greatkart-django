from django.urls import path
from . import views

urlpatterns = [
    path('', views.cart, name='cart'),
    path('add_cart/<int:product_id>/', views.add_cart, name='add_cart'),
    path('remove_cart/<int:product_id>/<int:cart_item_id>/', views.remove_cart, name='remove_cart'),
    path('remove_cart_item/<int:product_id>/<int:cart_item_id>/', views.remove_cart_item, name='remove_cart_item'),

    path('checkout/' , views.checkout , name='checkout' ) ,
    path('api/add/',views.api_add_to_cart,name='api_add_to_cart'),
    path('api/update/<int:cart_item_id>/',views.api_update_cart_item,name='api_update_cart_item'),
    path('api/remove/<int:cart_item_id>/',views.api_remove_cart_item,name='api_remove_cart_item'),
    path('api/clear/',views.api_clear_cart,name='api_clear_cart'),
    path('api/cart/', views.api_cart, name='api_cart'),
    path('api/checkout/',views.api_checkout,name='api_checkout'),
]