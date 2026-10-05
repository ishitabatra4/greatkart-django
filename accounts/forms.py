from django import forms
from .models import Account,UserProfile,VendorProfile


class RegistrationForm(forms.ModelForm):
    registration_type=forms.ChoiceField(
        choices=[
            ('customer','Customer'),
            ('vendor','Vendor'),
        ],
        widget=forms.RadioSelect
    )

    password=forms.CharField(widget=forms.PasswordInput(attrs={
        'placeholder':'Enter Password'
    }))

    confirm_password=forms.CharField(widget=forms.PasswordInput(attrs={
        'placeholder':'Confirm Password'
    }))

    gstin=forms.CharField(
        max_length=15,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder':'Enter GSTIN'
        })
    )

    class Meta:
        model=Account
        fields=[
            'first_name',
            'last_name',
            'phone_number',
            'email',
            'password'
        ]

    def __init__(self,*args,**kwargs):
        super(RegistrationForm,self).__init__(*args,**kwargs)

        for field in self.fields:
            self.fields[field].widget.attrs['class']='form-control'

    def clean_email(self):
        email=self.cleaned_data.get('email')

        if Account.objects.filter(email=email).exists():
            raise forms.ValidationError(
                'An account with this email already exists.'
            )

        return email

    def clean(self):
        cleaned_data=super(RegistrationForm,self).clean()

        password=cleaned_data.get('password')
        confirm_password=cleaned_data.get('confirm_password')
        registration_type=cleaned_data.get('registration_type')
        gstin=cleaned_data.get('gstin')

        if password!=confirm_password:
            self.add_error(
                'confirm_password',
                'Passwords do not match'
            )

        if registration_type=='vendor' and not gstin:
            self.add_error(
                'gstin',
                'GSTIN is required for vendors.'
            )

        return cleaned_data


class UserForm(forms.ModelForm):
    class Meta:
        model=Account
        fields=('first_name','last_name','phone_number')

    def __init__(self,*args,**kwargs):
        super(UserForm,self).__init__(*args,**kwargs)

        for field in self.fields:
            self.fields[field].widget.attrs['class']='form-control'


class UserProfileForm(forms.ModelForm):
    profile_picture=forms.ImageField(
        required=False,
        error_messages={'invalid':('Image files only')},
        widget=forms.FileInput
    )

    class Meta:
        model=UserProfile
        fields=(
            'address_line_1',
            'address_line_2',
            'city',
            'state',
            'country',
            'profile_picture'
        )

    def __init__(self,*args,**kwargs):
        super(UserProfileForm,self).__init__(*args,**kwargs)

        for field in self.fields:
            self.fields[field].widget.attrs['class']='form-control'

class VendorProfileForm(forms.ModelForm):

    class Meta:
        model=VendorProfile
        fields=(
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
        )

    def __init__(self,*args,**kwargs):
        super(VendorProfileForm,self).__init__(*args,**kwargs)

        for field in self.fields:
            self.fields[field].widget.attrs['class']='form-control'            