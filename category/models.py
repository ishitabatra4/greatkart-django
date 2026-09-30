from django.db import models
from django.urls import reverse
from accounts.models import Account

# Create your models here.
class Category(models.Model):
    category_name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField(max_length=255)
    cat_image = models.ImageField(upload_to='photos/categories', blank=True)
    is_approved=models.BooleanField(default=True)
    class Meta:
        verbose_name = 'category'
        verbose_name_plural = 'categories'

    def get_url(self):
            return reverse('products_by_category', args=[self.slug])   
    def __str__(self):
        return self.category_name

class CategoryRequest(models.Model):
    vendor=models.ForeignKey('accounts.Account',on_delete=models.CASCADE,related_name='category_requests')
    category_name=models.CharField(max_length=100)
    description=models.TextField(blank=True)
    status=models.CharField(
        max_length=20,
        choices=(
            ('pending','Pending'),
            ('approved','Approved'),
            ('rejected','Rejected'),
        ),
        default='pending'
    )
    created_at=models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.category_name