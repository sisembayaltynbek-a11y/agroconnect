from django.contrib import admin
from .models import Products, Categories, Farmer, Deliveries, Feedback, Buyer, CarDetails, ChatHistory

# Register your models here.
admin.site.register(Buyer)
admin.site.register(Products)
admin.site.register(Categories)
admin.site.register(Farmer)
admin.site.register(Deliveries)
admin.site.register(CarDetails)
admin.site.register(Feedback)
admin.site.register(ChatHistory)