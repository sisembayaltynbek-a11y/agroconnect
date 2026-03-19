from django.utils import timezone
from django.core.validators import MinValueValidator
from decimal import Decimal
from django.conf import settings
from django.db import models
from autoslug import AutoSlugField

class Categories(models.Model):
    name = models.CharField(max_length=255)
    image = models.ImageField(upload_to="category_images/", blank=True, null=True)
    excerpt = models.CharField(max_length=500, null=True, blank=True)

    def __str__(self):
        return self.name
    
# User accessibilities to become ...
class Location(models.Model):
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)

    def __str__(self):
        return f"{self.latitude}, {self.longitude}"

class Buyer(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    name = models.CharField(max_length=50)
    liked_products = models.ManyToManyField(
        'Products',
        blank=True,
        related_name='liked_by'
    )

    def __str__(self):
        return self.name

class Farmer(models.Model):
    buyer = models.OneToOneField(Buyer, on_delete=models.CASCADE)
    brand = models.CharField()
    phonenumber = models.CharField(max_length=15, blank=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    location = models.ForeignKey(Location, on_delete=models.CASCADE, null=True, blank=True)
    license = models.ImageField(upload_to='licenses/', blank=True, null=True)

    def __str__(self):
        return self.brand

class CarDetails(models.Model):
    carname = models.CharField(max_length=255)
    carnumber = models.CharField(max_length=10)
    vehicle_registration = models.ImageField(upload_to='vehicle_registrations/')
    insurance = models.ImageField(upload_to='insurancies/')
    medical_certificate = models.ImageField(upload_to='insurancies/')
    
    def __str__(self):
        return self.carnumber

class Deliveries(models.Model):
    buyer = models.OneToOneField(Buyer, on_delete=models.CASCADE)
    vehicle = models.OneToOneField(CarDetails, on_delete=models.CASCADE)
    fullname = models.CharField()
    image = models.ImageField(upload_to="delivery_images/", blank=True, null=True)
    STATUS_CHOICES = [
        (1, 'Beginner'),
        (2, 'Intermediate'),
        (3, 'Professional'),
    ]
    working_stage = models.IntegerField(choices=STATUS_CHOICES)
    recommendation = models.TextField()

    def __str__(self):
        return self.fullname

class Products(models.Model):
    image = models.ImageField(upload_to="products/", null=True, blank=True)
    farmer = models.ForeignKey(Farmer, on_delete=models.CASCADE)
    name = models.CharField(max_length=120)
    slug = AutoSlugField(populate_from='name', unique=True, always_update=False)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    excerpt = models.CharField(max_length=200, null=True, blank=True)
    description = models.TextField()
    harvest_date = models.DateField(default=timezone.now)
    category = models.ForeignKey(Categories, on_delete=models.CASCADE)

    def __str__(self):
        return self.name
    
class Feedback(models.Model):
    buyer = models.ForeignKey(Buyer, on_delete=models.CASCADE, related_name='given_feedbacks')
    product = models.ForeignKey(Products, on_delete=models.CASCADE, related_name='received_feedbacks')
    rating = models.IntegerField(
        choices=[(i, f'{i} Stars') for i in range(1, 6)],
        default=5
    )
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['buyer', 'product'], name='unique_feedback')
        ]

class Order(models.Model):
    buyer = models.ForeignKey(Buyer, on_delete=models.CASCADE)
    delivery = models.ForeignKey(Deliveries, on_delete=models.SET_NULL, null=True)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)