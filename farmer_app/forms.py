from django.contrib.auth.models import User
from django import forms
from .models import Products
from django.core.validators import MinValueValidator
from decimal import Decimal

class AddFarmProduct(forms.ModelForm):
    class Meta:
        model = Products
        exclude = ('farmer', 'slug')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs) # Call only once
        self.fields['price'].widget.attrs.update({'step': '0.01', 'min': '0.01'})
        self.fields['harvest_date'].widget.attrs.update({'placeholder': 'YYYY-MM-DD'})
        
class BuyerSignUpForm(forms.Form):
    username = forms.CharField(max_length=150)
    email = forms.EmailField()
    password1 = forms.CharField(widget=forms.PasswordInput, label="Password")
    password2 = forms.CharField(widget=forms.PasswordInput, label="Confirm Password")
    avatar = forms.ImageField(required=False)
    name = forms.CharField(max_length=100, label="Full Name")

    def clean(self):
        cleaned_data = super().clean()
        
        if cleaned_data.get("password1") != cleaned_data.get("password2"):
            raise forms.ValidationError("Passwords do not match")

        if User.objects.filter(username=cleaned_data.get("username")).exists():
            raise forms.ValidationError("Username already exists")

        if User.objects.filter(email=cleaned_data.get("email")).exists():
            raise forms.ValidationError("Email already registered")

        return cleaned_data

class FarmerSignUpForm(forms.Form):
    phonenumber = forms.CharField(max_length=15, required=False, label="Phone Number")
    address = forms.CharField(required=False)
    license = forms.ImageField(required=False)
    latitude = forms.FloatField(required=False)
    longitude = forms.FloatField(required=False)

    def clean(self):
        cleaned_data = super().clean()
        lat = cleaned_data.get("latitude")
        lng = cleaned_data.get("longitude")

        if lat is not None and not (-90 <= lat <= 90):
            raise forms.ValidationError("Latitude must be between -90 and 90")

        if lng is not None and not (-180 <= lng <= 180):
            raise forms.ValidationError("Longitude must be between -180 and 180")

        return cleaned_data

class DeliverySignUpForm(forms.Form):
    carname = forms.CharField(max_length=255)
    carnumber = forms.CharField(max_length=10)

    vehicle_registration = forms.ImageField()
    insurance = forms.ImageField()
    medical_certificate = forms.ImageField()

    working_stage = forms.ChoiceField(choices=[
        (1, 'Beginner'),
        (2, 'Intermediate'),
        (3, 'Professional'),
    ])