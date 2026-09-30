from rest_framework import serializers
from accounts.models import Account,VendorProfile


class RegisterSerializer(serializers.ModelSerializer):

    password=serializers.CharField(write_only=True)
    confirm_password=serializers.CharField(write_only=True)

    registration_type=serializers.ChoiceField(
        choices=[
            ('customer','Customer'),
            ('vendor','Vendor'),
        ]
    )

    store_name=serializers.CharField(required=False,allow_blank=True)
    store_description=serializers.CharField(required=False,allow_blank=True)
    store_logo=serializers.ImageField(required=False,allow_null=True)

    class Meta:
        model=Account
        fields=[
            'first_name',
            'last_name',
            'phone_number',
            'email',
            'password',
            'confirm_password',
            'registration_type',
            'store_name',
            'store_description',
            'store_logo',
        ]

    def validate_email(self,value):
        if Account.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                'An account with this email already exists.'
            )

        return value

    def validate(self,data):
        if data['password']!=data['confirm_password']:
            raise serializers.ValidationError(
                'Passwords do not match.'
            )

        if data['registration_type']=='vendor' and not data.get('store_name'):
            raise serializers.ValidationError(
                'Store name is required for vendors.'
            )

        return data

    def create(self,validated_data):

        registration_type=validated_data.pop('registration_type')

        password=validated_data.pop('password')
        validated_data.pop('confirm_password')

        store_name=validated_data.pop('store_name','')
        store_description=validated_data.pop('store_description','')
        store_logo=validated_data.pop('store_logo',None)

        email=validated_data['email']

        username=email.split('@')[0]

        if Account.objects.filter(username=username).exists():
            username=username+str(Account.objects.count()+1)

        user=Account.objects.create_user(
            username=username,
            password=password,
            **validated_data
        )

        user.is_vendor=registration_type=='vendor'
        user.is_active=False
        user.save()

        if registration_type=='vendor':
            VendorProfile.objects.create(
                user=user,
                store_name=store_name,
                store_description=store_description,
                store_logo=store_logo,
                is_approved=False
            )

        return user