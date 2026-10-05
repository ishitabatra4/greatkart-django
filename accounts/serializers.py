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

    gstin=serializers.CharField(
        max_length=15,
        required=False,
        allow_blank=True
    )

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
            'gstin',
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

        if data['registration_type']=='vendor' and not data.get('gstin'):
            raise serializers.ValidationError(
                'GSTIN is required for vendors.'
            )

        return data

    def create(self,validated_data):

        registration_type=validated_data.pop('registration_type')

        password=validated_data.pop('password')
        validated_data.pop('confirm_password')

        gstin=validated_data.pop('gstin','')

        email=validated_data['email']
        phone_number=validated_data.pop('phone_number')

        username=email.split('@')[0]

        if Account.objects.filter(username=username).exists():
            username=username+str(Account.objects.count()+1)

        user=Account.objects.create_user(
            username=username,
            password=password,
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            email=email
        )

        user.phone_number=phone_number
        user.is_vendor=registration_type=='vendor'
        user.is_active=False
        user.save()

        if registration_type=='vendor':
            VendorProfile.objects.create(
                user=user,
                gstin=gstin,
                is_approved=False
            )

        return user

class VendorProfileSerializer(serializers.ModelSerializer):

    class Meta:
        model=VendorProfile
        fields=[
            'gstin',
            'store_name',
            'business_type',
            'pan',
            'address_line_1',
            'address_line_2',
            'city',
            'state',
            'pincode',
            'account_holder_name',
            'account_number',
            'ifsc_code',
            'bank_name',
            'shipping_method',
            'shipping_charges',
            'return_policy',
            'is_approved',
        ]

        read_only_fields=[
            'is_approved',
        ]