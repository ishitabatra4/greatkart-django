from django.contrib import admin
from django.utils.text import slugify

from .models import Category,CategoryRequest


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):

    list_display=(
        'category_name',
        'slug',
        'is_approved'
    )

    list_filter=(
        'is_approved',
    )

    search_fields=(
        'category_name',
    )

    prepopulated_fields={
        'slug':('category_name',)
    }


@admin.register(CategoryRequest)
class CategoryRequestAdmin(admin.ModelAdmin):

    list_display=(
        'category_name',
        'vendor',
        'status',
        'created_at'
    )

    list_filter=(
        'status',
        'created_at'
    )

    search_fields=(
        'category_name',
        'vendor__email'
    )

    actions=[
        'approve_categories',
        'reject_categories'
    ]


    def approve_categories(self,request,queryset):

        for request_obj in queryset:

            category,created=Category.objects.get_or_create(
                category_name__iexact=request_obj.category_name,
                defaults={
                    'category_name':request_obj.category_name,
                    'slug':slugify(request_obj.category_name),
                    'description':request_obj.description,
                    'is_approved':True
                }
            )

            category.is_approved=True

            if request_obj.description:
                category.description=request_obj.description

            category.save()

            request_obj.status='approved'
            request_obj.save()


        self.message_user(
            request,
            'Selected category requests approved.'
        )


    approve_categories.short_description='Approve selected categories'


    def reject_categories(self,request,queryset):

        queryset.update(
            status='rejected'
        )

        self.message_user(
            request,
            'Selected category requests rejected.'
        )


    reject_categories.short_description='Reject selected categories'