from django.urls import path
from . import views

urlpatterns=[
    path('request-category/',views.request_category,name='request_category'),
    path('api/vendor/request-category/',views.api_request_category,name='api_request_category'),
    path('api/categories/',views.api_categories,name='api_categories'),
]
