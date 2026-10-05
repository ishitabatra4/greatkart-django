from rest_framework import serializers
from .models import Product


class ProductSerializer(serializers.ModelSerializer):

    category_name=serializers.CharField(
        source='category.category_name',
        read_only=True
    )

    vendor_name=serializers.CharField(
        source='vendor.username',
        read_only=True
    )

    class Meta:
        model=Product
        fields=[
            'id',
            'product_name',
            'brand',
            'slug',
            'description',
            'price',
            'stock',
            'images',
            'is_available',
            'category',
            'category_name',
            'vendor',
            'vendor_name',
            'created_date',
            'modified_date',
        ]
        read_only_fields=[
            'vendor',
            'slug',
            'created_date',
            'modified_date',
        ]