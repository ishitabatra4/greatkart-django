from django.contrib import admin
from .models import Cart, CartItem  

# Register your models here.
class CartAdmin(admin.ModelAdmin):
    list_display = ('cart_id', 'date_added')
    list_per_page = 20

class CartItemAdmin(admin.ModelAdmin):
    list_display = ('product', 'cart', 'quantity', 'is_active')
    list_editable = ('quantity', 'is_active')
    list_per_page = 20

admin.site.register(Cart,CartAdmin)
admin.site.register(CartItem,CartItemAdmin)
