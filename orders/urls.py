from django.urls import path
from . import views

urlpatterns=[
    path('place_order/',views.place_order,name='place_order'),
    path('payments/',views.payments,name='payments'),
    path('confirm_payment/',views.confirm_payment,name='confirm_payment'),
    path('order_complete/<str:order_number>/',views.order_complete,name='order_complete'),
    path('api/place-order/',views.api_place_order,name='api_place_order'),
    path('api/payments/', views.api_payments, name='api_payments'),
    path('api/confirm-payment/',views.api_confirm_payment,name='api_confirm_payment'),
    path('api/admin/orders/',views.api_admin_orders,name='api_admin_orders'),
    path('api/admin/orders/<str:order_number>/',views.api_admin_order_detail,name='api_admin_order_detail'),
    path('api/admin/orders/<str:order_number>/status/',views.api_admin_order_status,name='api_admin_order_status'),
    path('api/admin/orders/<str:order_number>/delete/',views.api_admin_order_delete,name='api_admin_order_delete'),
    path('api/admin/payments/',views.api_admin_payments,name='api_admin_payments'),
    path('api/admin/payments/<int:payment_id>/',views.api_admin_payment_detail,name='api_admin_payment_detail'),
    path('api/order-complete/<str:order_number>/',views.api_order_complete,name='api_order_complete'),
]