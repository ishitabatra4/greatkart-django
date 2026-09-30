from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Account,UserProfile,VendorProfile
from django.utils.html import format_html

# Register your models here.

class AccountAdmin(UserAdmin):
    list_display=('first_name','last_name','username','email','is_vendor','is_active','date_joined')
    list_display_links=('first_name','last_name','email')
    list_filter=('is_vendor','is_active')
    readonly_fields=('last_login','date_joined')
    ordering=('-date_joined',)
    filter_horizontal=()

    fieldsets=(
        ('Personal Info',{'fields':('first_name','last_name','username','email','phone_number')}),
        ('Permissions',{'fields':('is_active','is_staff','is_admin','is_superadmin','is_vendor')}),
        ('Important Dates',{'fields':('last_login','date_joined')}),
    )

class UserProfileAdmin(admin.ModelAdmin):
    def thumbnail(self,object):
        if object.profile_picture and object.profile_picture.name:
            return format_html(
                '<img src="{}" width="30" height="30" style="border-radius:50%;object-fit:cover;">'.format(
                    object.profile_picture.url
                )
            )
        return '-'

    thumbnail.short_description='Profile Picture'
    list_display=('thumbnail','user','city','state','country')

class VendorProfileAdmin(admin.ModelAdmin):
    list_display=('store_name','user','approval_status','created_at')
    list_filter=('is_approved',)
    search_fields=('store_name','user__email')
    actions=['approve_vendors','reject_vendors']

    def approval_status(self,obj):
        if obj.is_approved:
            return format_html(
                '<span style="color:green;font-weight:bold;">✓ Approved</span>'
            )
        return format_html(
            '<span style="color:#dc3545;font-weight:bold;">✗ Pending</span>'
        )

    approval_status.short_description='Status'

    def approve_vendors(self,request,queryset):
        queryset.update(is_approved=True)
        self.message_user(request,'Selected vendors approved successfully.')

    approve_vendors.short_description='Approve selected vendors'

    def reject_vendors(self,request,queryset):
        queryset.update(is_approved=False)
        self.message_user(request,'Selected vendors rejected.')

    reject_vendors.short_description='Reject selected vendors'

admin.site.register(Account,AccountAdmin)
admin.site.register(UserProfile,UserProfileAdmin)
admin.site.register(VendorProfile,VendorProfileAdmin)