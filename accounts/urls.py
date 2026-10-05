from django.urls import path
from . import views
from rest_framework_simplejwt.views import TokenObtainPairView,TokenRefreshView,TokenBlacklistView


urlpatterns=[

    path('register/',views.register,name='register'),
    path('login/',views.login,name='login'),
    path('logout/',views.logout,name='logout'),

    path('dashboard/',views.dashboard,name='dashboard'),
    path('',views.dashboard,name='dashboard'),
    path('profile/',views.profile,name='profile'),

    path('activate/<uidb64>/<token>/',views.activate,name='activate'),

    path('my_orders/',views.my_orders,name='my_orders'),
    path('edit_profile/',views.edit_profile,name='edit_profile'),
    path('change_password/',views.change_password,name='change_password'),
    path('order_detail/<int:order_id>/',views.order_detail,name='order_detail'),
    path('forgot-password/',views.forgot_password,name='forgot_password'),
    path('reset-password/',views.reset_password,name='reset_password'),

    path('vendor/orders/',views.vendor_orders,name='vendor_orders'),


    # JWT

    path('api/token/',TokenObtainPairView.as_view(),name='token_obtain_pair'),
    path('api/token/refresh/',TokenRefreshView.as_view(),name='token_refresh'),
    path('api/me/',views.api_me,name='api_me'),
    path('api/profile/',views.api_profile,name='api_profile'),
    path('api/register/',views.RegisterAPIView.as_view(),name='api_register'),
    path('api/logout/',TokenBlacklistView.as_view(),name='api_logout'),
    path('api/customer-test/',views.api_customer_test,name='api_customer_test'),
    path('api/vendor-test/',views.api_vendor_test,name='api_vendor_test'),
    path('api/vendor/profile/',views.api_vendor_profile,name='api_vendor_profile'),
    path('api/forgot-password/',views.api_forgot_password,name='api_forgot_password'),
    path('api/reset-password/', views.api_reset_password, name='api_reset_password'),
    path('api/change-password/',views.api_change_password,name='api_change_password'),
    path('api/orders/',views.api_my_orders,name='api_my_orders'),
    path('api/orders/<str:order_number>/',views.api_order_detail,name='api_order_detail'),
    path('api/vendor/orders/',views.api_vendor_orders,name='api_vendor_orders'),
    path('api/vendor/orders/<str:order_number>/',views.api_vendor_order_detail,name='api_vendor_order_detail'),

]