from django import forms
from .models import Product
from category.models import Category
from .models import ReviewRating


class ProductForm(forms.ModelForm):
    class Meta:
        model=Product
        fields=(
            'product_name',
            'brand',
            'description',
            'price',
            'stock',
            'category',
            'images',
            'is_available',
        )
        widgets={
            'description':forms.Textarea(attrs={'rows':4}),
        }

    def __init__(self,*args,**kwargs):
        super(ProductForm,self).__init__(*args,**kwargs)

        self.fields['category'].queryset=Category.objects.filter(is_approved=True)

        for field in self.fields:
            self.fields[field].widget.attrs['class']='form-control'


class ReviewForm(forms.ModelForm):
    class Meta:
        model=ReviewRating
        fields=['subject','review','rating']