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

class Deliveries(models.Model):
    fullname = models.CharField(max_length=255)
    image = models.ImageField(upload_to="delivery_images/", blank=True, null=True)
    working_stage = models.IntegerField()
    recommendation = models.TextField()

    def __str__(self):
        return self.fullname

class Farmer(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50, blank=True)
    phonenumber = models.CharField(max_length=15)
    address = models.CharField(max_length=255, null=True, blank=True)
    liked_products = models.ManyToManyField(
        'Products',
        blank=True,
        related_name='liked_by'
    )

    def __str__(self):
        return f"{self.name} {self.last_name}"


class Products(models.Model):
    image = models.ImageField(upload_to="products/", null=True, blank=True)
    farmer = models.ForeignKey(Farmer, on_delete=models.CASCADE)
    name = models.CharField(max_length=120)
    slug = AutoSlugField(populate_from='name', unique=True)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    excerpt = models.CharField(max_length=200, null=True, blank=True)
    description = models.TextField()
    harvest_date = models.DateField()
    category = models.ForeignKey(Categories, on_delete=models.CASCADE)

    def __str__(self):
        return self.name
    
class Feedback(models.Model):
    farmer = models.ForeignKey(
        Farmer,
        on_delete=models.CASCADE,
        related_name='given_feedbacks'
    )
    product = models.ForeignKey(
        Products,
        on_delete=models.CASCADE,
        related_name='received_feedbacks'
    )
    rating = models.IntegerField(
        choices=[(1, '1 Star'), (2, '2 Stars'), (3, '3 Stars'), 
                 (4, '4 Stars'), (5, '5 Stars')],
        default=5
    )
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['farmer', 'product']  # One feedback per farmer per product
    
    def __str__(self):
        return f"{self.farmer.name}'s feedback for {self.product.name}"