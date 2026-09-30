from django.urls import path
from . import views

urlpatterns=[
    path('request-category/',views.request_category,name='request_category'),
]