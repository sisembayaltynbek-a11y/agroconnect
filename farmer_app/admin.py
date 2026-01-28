from django.contrib import admin
from .models import Products, Categories, Farmer, Deliveries, Feedback

# Register your models here.
admin.site.register(Products)
admin.site.register(Categories)
admin.site.register(Farmer)
admin.site.register(Deliveries)
admin.site.register(Feedback)