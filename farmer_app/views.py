from decimal import Decimal
import json
from django.http import Http404, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from allauth.account.views import LoginView, LogoutView
from django.views import View
from django.views.generic import CreateView, FormView
from django.urls import reverse_lazy
from django.contrib.auth import login
from django.db import transaction
from django.views.decorators.http import require_POST
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from openai import OpenAI
import requests

from .models import Buyer, Deliveries, Location, Products, Categories, Farmer, Feedback
from .forms import AddFarmProduct, BuyerSignUpForm, FarmerSignUpForm
from django.utils.decorators import method_decorator

from django.views.generic import DeleteView, UpdateView
from django.db.models import Avg

import random
import stripe
import os
from django.conf import settings
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.urls import reverse


class Index(View):
    API_KEY = os.getenv('OPENROUTER_API_KEY')
    ai_model = "google/gemma-3n-e2b-it:free"
    template_name = "home.html"

    def get(self, request):
        return render(request, self.template_name, {
            'categories': Categories.objects.all(),
            'deliveries': Deliveries.objects.filter(working_stage__gte=3),
            'popular_products': Products.objects.all().order_by('-id')[:8],
            'cheap_products': Products.objects.filter(price__lt=Decimal('700.00'))[:8],
            # 'planting_areas': planting_areas,
            'ai_response': None,
        })
    
    def post(self, request):
        user_input = request.POST.get("user_input", "")
        # planting_areas = self.ai_best_planting()
        
        return render(request, self.template_name, {
            'categories': Categories.objects.all(),
            'deliveries': Deliveries.objects.filter(working_stage__gte=3),
            'popular_products': Products.objects.all().order_by('-id')[:8],
            'cheap_products': Products.objects.filter(price__lt=Decimal('500.00'))[:8],
            # 'planting_areas': planting_areas,
            'ai_response': self.get_response(user_input),
            'user_input': user_input
        })

    # def ai_best_planting(self):
    #     client = OpenAI(
    #         base_url="https://openrouter.ai/api/v1",
    #         api_key=self.API_KEY
    #     )

    #     try:
    #         completion = client.chat.completions.create(
    #             model="deepseek/deepseek-r1-distill-qwen-32b",
    #             messages=[
    #                 {
    #                     "role": "user",
    #                     "content": """
    #                     Return ONLY valid JSON.

    #                     Give the best 10 planting areas in Kazakhstan today.

    #                     Format example:
    #                     {
    #                     "locations":[
    #                         {"lat":43.2220,"lng":76.8512},
    #                         {"lat":42.9000,"lng":71.3667}
    #                     ]
    #                     }
    #                     """
    #                 }
    #             ]
    #         )

    #         result = completion.choices[0].message.content

    #         return json.loads(result)

    #     except Exception as e:
    #         print(e)
    #         return {"locations": []}
        
    def get_response(self, user_input):
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.API_KEY
        )
        try:
            completion = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": "<YOUR_SITE_URL>",
                "X-Title": "<YOUR_SITE_NAME>",
            },
            extra_body={},
            model=self.ai_model,
            messages=[
                {
                "role": "user",
                "content": f"""
                    You are an AI agricultural expert helping farmers in Kazakhstan.

                    User question:
                    {user_input}

                    Give short practical farming advice.
                """
                }
                ]
            )
            print(completion.choices[0].message.content)
        except Exception as e:
            print(f"Error getting AI response: {e}")
            return "try again!"
                
        print(completion.choices[0].message.content)
        return str(completion.choices[0].message.content)

def ai_detector(request, product_id):
    product = get_object_or_404(Products, id=product_id)
    image_path = request.build_absolute_uri(product.image.url)
    response = None

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=Index.API_KEY
    )

    try:
        completion = client.chat.completions.create(
            model=Index.ai_model,
            max_tokens=300,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Analyze this plant image. Identify possible disease and suggest treatment."},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_path
                            }
                        }
                    ]
                }
            ]
        )

        response = completion.choices[0].message.content

    except Exception:
        response = "Disease detection unavailable"

    return render(request, "product_details.html", {
        "product": product,
        "response": response
    })

def category_products(request, id):
    category = get_object_or_404(Categories, id=id)
    products = Products.objects.filter(category=category)
    return render(request, 'category.html', {
        'category': category,
        'products': products
    })

def ai_price_advisor(request, product_name):
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=Index.API_KEY
    )
    try:
        completion = client.chat.completions.create(
            model=Index.ai_model,
            messages=[
                {
                    "role": "user",
                    "content": f"Suggest a reasonable market price for {product_name} in Kazakhstan farm markets. Return only a number in KZT."
                }
            ]
        )
        suggestion = completion.choices[0].message.content
    except Exception as e:
        print(e)
        suggestion = "Price suggestion unavailable"

    return JsonResponse({
        "product": product_name,
        "suggested_price": suggestion
    })

class AddProductView(LoginRequiredMixin, CreateView):
    model = Products
    form_class = AddFarmProduct
    template_name = "sell.html"
    success_url = reverse_lazy("home")

    def form_valid(self, form):
        buyer = getattr(self.request.user, "buyer", None)
        if not buyer:
            messages.error(self.request, "You need a buyer profile first.")
            return redirect("home")
        farmer = getattr(buyer, "farmer", None)
        if not farmer:
            messages.error(self.request, "You must become a farmer to sell.")
            return redirect("become-farmer")
        form.instance.farmer = farmer
        return super().form_valid(form)
    
class Login(LoginView):
    template_name = 'account/login.html'

    def get_success_url(self):
        return reverse_lazy('home')

from django.contrib.auth import login
from django.contrib.auth import authenticate

class BuyerSignUpView(FormView):
    template_name = "account/signup.html"
    form_class = BuyerSignUpForm
    success_url = reverse_lazy("home")

    @transaction.atomic
    def form_valid(self, form):

        user = User.objects.create_user(
            username=form.cleaned_data["username"],
            email=form.cleaned_data["email"],
            password=form.cleaned_data["password1"],
        )

        Buyer.objects.create(
            user=user,
            avatar=form.cleaned_data["avatar"],
            name=form.cleaned_data["name"],
        )

        user = authenticate(
            self.request,
            username=form.cleaned_data["username"],
            password=form.cleaned_data["password1"]
        )

        if user is not None:
            login(self.request, user)

        return redirect(self.success_url)
    
class BecomeFarmerView(LoginRequiredMixin, FormView):
    template_name = "account/become_farmer.html"
    form_class = FarmerSignUpForm
    success_url = reverse_lazy("profile")

    def form_valid(self, form):

        buyer = getattr(self.request.user, "buyer", None)

        latitude = form.cleaned_data.get("latitude")
        longitude = form.cleaned_data.get("longitude")

        location = None
        if latitude and longitude:
            location = Location.objects.create(
                latitude=latitude,
                longitude=longitude
            )

        Farmer.objects.create(  
            buyer=buyer,
            phonenumber=form.cleaned_data["phonenumber"],
            address=form.cleaned_data["address"],
            location=location,
        )

        messages.success(self.request, "You are now a farmer!")

        return redirect(self.success_url)
            
class Logout(LogoutView):
    template_name = 'account/logout.html'

def subsidy_page(request):
    return render(request, 'support.html')

def products(request):
    products_list = Products.objects.all()
    return render(request, 'products.html', {
        'products': products_list,
        'categories': Categories.objects.all()
    })

def ai_recommend_products(product):
    return Products.objects.filter(
        category=product.category
    ).exclude(id=product.id).order_by('?')[:4]

def product_details(request, slug):
    product = get_object_or_404(Products, slug=slug)
    feedbacks = product.received_feedbacks.select_related('buyer').order_by('-created_at')

    buyer = None
    can_give_feedback = False
    is_liked = False

    if request.user.is_authenticated:
        buyer = getattr(request.user, "buyer", None)
        if buyer:
            is_liked = buyer.liked_products.filter(id=product.id).exists()
            already_reviewed = Feedback.objects.filter(
                buyer=buyer,
                product=product
            ).exists()
            can_give_feedback = not already_reviewed
        else:
            is_liked = False
            can_give_feedback = False

    if request.method == "POST" and buyer and can_give_feedback:
        rating = request.POST.get("rating")
        comment = request.POST.get("comment")

        Feedback.objects.create(
            buyer=buyer,
            product=product,
            rating=rating,
            comment=comment
        )
        messages.success(request, "Thank you for your feedback!")
        return redirect("product-details", slug=slug)

    return render(request, "product_details.html", {
        "buyer": buyer,
        "product": product,
        "feedbacks": feedbacks,
        "can_give_feedback": can_give_feedback,
        "is_liked": is_liked,
        "likes_count": product.liked_by.count(),
    })

def search(request):
    searched = request.POST.get('searched')
    results = Products.objects.filter(name__icontains=searched)
    return render(request, 'search_results.html', {
        'searched': searched,
        'results': results
    })

@login_required
def cart(request):
    cart = request.session.get('cart', {})
    
    # Calculate totals
    subtotal = 0.0
    cart_items = {}
    
    for pid, item in cart.items():
        # Convert price to float to ensure it's numeric
        price = float(item['price'])
        qty = int(item.get('qty', 1))
        item['id'] = pid
        item['price'] = price
        item['qty'] = qty  # Update with float value
        item['total'] = price * qty
        subtotal += item['total']
        cart_items[pid] = item
    
    total = subtotal
    
    return render(request, 'cart.html', {
        'cart': cart_items,
        'subtotal': subtotal,
        'total': total
    })

@login_required
@require_POST
def add_to_cart(request, product_id):
    product = get_object_or_404(Products, id=product_id)
    quantity = int(request.POST.get('quantity', 1))

    cart = request.session.get('cart', {})
    pid = str(product.id)

    if pid in cart:
        cart[pid]['qty'] += quantity
    else:
        cart[pid] = {
            'name': product.name,
            'price': float(product.price),
            'qty': quantity,
        }

    request.session['cart'] = cart
    messages.success(request, f"{product.name} added to cart")
    return redirect(reverse_lazy('cart'))

stripe.api_key = settings.STRIPE_SECRET_KEY

@login_required
def create_checkout_session(request):
    cart = request.session.get('cart', {})
    if not cart:
        return redirect('cart')

    available_deliveries = Deliveries.objects.all()
    if available_deliveries.exists():
        selected_delivery = random.choice(available_deliveries)
        request.session['assigned_delivery_id'] = selected_delivery.id
    
    DELIVERY_FEE_KZT = 500 
    
    line_items = []
    
    for pid, item in cart.items():
        unit_amount = int(float(item['price']) * 100)
        line_items.append({
            'price_data': {
                'currency': 'kzt',
                'product_data': {'name': item['name']},
                'unit_amount': unit_amount,
            },
            'quantity': item['qty'],
        })

    line_items.append({
        'price_data': {
            'currency': 'kzt',
            'product_data': {
                'name': 'Delivery Fee',
                'description': 'Flat rate shipping to your location',
            },
            'unit_amount': DELIVERY_FEE_KZT * 100,
        },
        'quantity': 1,
    })

    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=line_items,
            mode='payment',
            success_url=request.build_absolute_uri(reverse('payment_success')),
            cancel_url=request.build_absolute_uri(reverse('cart')),
        )
        return redirect(checkout_session.url, code=303)
    except Exception as e:
        return render(request, 'error.html', {'error': str(e)})
    
@login_required
def payment_success(request):
    delivery_id = request.session.get('assigned_delivery_id')
    delivery_person = None
    
    if delivery_id:
        delivery_person = Deliveries.objects.get(id=delivery_id)
    
    if 'cart' in request.session:
        del request.session['cart']
        
    return render(request, 'success.html', {'delivery_person': delivery_person})

@login_required
@require_POST
def increase_quantity(request, product_id):
    product = get_object_or_404(Products, id=product_id) 
    cart = request.session.get('cart', {}) 
    pid = str(product.id) # Use string as key for consistency 

    if pid in cart: 
        cart[pid]['qty'] += 1
        
    request.session['cart'] = cart
    return redirect(reverse_lazy('cart'))


@login_required
def toggle_like(request, product_id):
    product = get_object_or_404(Products, id=product_id)
    buyer = getattr(request.user, "buyer", None)
    if not buyer:
        messages.error(request, "You must have a buyer account to like products.")
        return redirect("login")
    if buyer.liked_products.filter(id=product.id).exists():
        buyer.liked_products.remove(product)
    else:
        buyer.liked_products.add(product)
    return redirect(request.META.get("HTTP_REFERER", "products"))

def delete_cart_item(request, pk):
    """Delete an item from the cart"""
    cart = request.session.get('cart', {})
    pid = str(pk)  # Ensure we're using string key
    
    if pid in cart:
        try:
            product = Products.objects.get(id=pk)
            del cart[pid]
            request.session['cart'] = cart
            messages.success(request, f"{product.name} removed from cart")
        except Products.DoesNotExist:
            messages.error(request, "Product not found")
    
    return redirect('cart')

# @login_required
# def profile(request):
#     try:
#         farmer = Farmer.objects.get(user=request.user)
#         products = Products.objects.filter(farmer=farmer)

#         context = {
#             'farmer': farmer,
#             'products': products,
#         }
        
#         return render(request, 'profile.html', context)
    
#     except Farmer.DoesNotExist:
#         return render(request, 'error.html', {'message': 'Farmer profile not found'})    

@login_required
def profile(request):
    buyer = getattr(request.user, "buyer", None)
    if not buyer:
        return render(request, "profile.html", {
            "buyer": None,
            "farmer": None,
            "products": [],
            "average_rate": "No data"
        })
    
    farmer = getattr(buyer, "farmer", None)
    products = Products.objects.filter(farmer=farmer) if farmer else []
    average_rate = Feedback.objects.filter(
        product__farmer=farmer
    ).aggregate(avg=Avg('rating'))['avg']

    return render(request, "profile.html", {
        "buyer": buyer,
        "farmer": farmer,
        "products": products,
        "average_rate": round(average_rate, 1) if average_rate else "No ratings"
    })

@login_required
def delete_self_published(request, product_id):
    buyer = getattr(request.user, "buyer", None)
    farmer = getattr(buyer, "farmer", None)
    product = get_object_or_404(Products, id=product_id)

    if not farmer:
        messages.error(request, "Farmer profile not found.")
        return redirect("profile")

    if product.farmer != farmer:
        messages.error(request, "You can only delete your own products!")
        return redirect("profile")

    product.delete()
    messages.success(request, "Product deleted!")
    return redirect("profile")

def choose_page(request):
    buyer = getattr(request.user, "buyer", None)
    farmer = getattr(buyer, "farmer", None)
    return render(request, 'choice.html', {
        'buyer': buyer,
        'farmer': farmer,
    })

class UpdatePost(LoginRequiredMixin, UpdateView):
    model = Products
    fields = ['image', 'name', 'price', 'excerpt', 'description', 'category']
    template_name = 'update.html'
    success_url = reverse_lazy('products')
    def get_queryset(self):
        buyer = getattr(self.request.user, "buyer", None)
        farmer = getattr(buyer, "farmer", None)
        if farmer:
            return Products.objects.filter(farmer=farmer)
        return Products.objects.none()

class UpdateBuyer(LoginRequiredMixin, UpdateView):
    model = Buyer
    fields = ['name', 'avatar']
    template_name = 'update_buyer.html'
    success_url = reverse_lazy('update-page-buyer')  # redirect after success

    def get_object(self):
        buyer = getattr(self.request.user, "buyer", None)
        if not buyer:
            raise Http404("Buyer profile not found")
        return buyer

class UpdateFarmer(LoginRequiredMixin, UpdateView):
    model = Farmer
    fields = ['phonenumber', 'address']
    template_name = 'update.html'
    success_url = reverse_lazy('profile')

    def get_object(self):
        buyer = getattr(self.request.user, "buyer", None)
        if not buyer:
            raise Http404("Buyer profile not found")
        farmer = getattr(buyer, "farmer", None)
        if not farmer:
            raise Http404("Farmer profile not found")
        return farmer
    
    def latlng_former(self, location_name): 
        client = OpenAI( base_url="https://openrouter.ai/api/v1", api_key=Index.API_KEY ) 
        _isResponse = False
        try: 
            completion = client.chat.completions.create( 
                model=Index.ai_model,
                messages=[ { 
                    "role": "user", 
                    "content": f""" 
                    Return ONLY valid Text. 
                    Give the latitude and longitude of the {location_name}. 
                    only like this without letters and words
                    Format example: "43.2220,76.8512" 
                    """ 
                    } ] 
                )
            suggestion = completion.choices[0].message.content.split(',') 
        except Exception as e: 
            print(e) 
            suggestion = "43.2220,76.8512"
        return suggestion 
    
    def form_valid(self, form):
        response = super().form_valid(form)
        location_name = self.request.POST.get("location")
        if location_name:
            lat_lng = self.latlng_former(location_name)
            if isinstance(lat_lng, list) and len(lat_lng) >= 2:
                if self.object.location:
                    self.object.location.latitude = float(lat_lng[0].strip())
                    self.object.location.longitude = float(lat_lng[1].strip())
                    self.object.location.save()
                else:
                    new_location = Location.objects.create(
                        latitude=float(lat_lng[0].strip()),
                        longitude=float(lat_lng[1].strip())
                    )
                    self.object.location = new_location
                    self.object.save()
        return response
            
def iot_dashboard(request):
    city_name = request.POST.get('city_name', 'Almaty')
    url = f"https://api.openweathermap.org/data/2.5/forecast?q={city_name}&appid=89c57e8dfcd68a00c8b51ce244feff28&units=metric"
    response = requests.get(url)
    data = response.json()

    forecast = data['list'][0]  # first forecast record

    sendings = {
        "city": city_name,
        "datetime": forecast['dt_txt'],

        # main weather data
        "temp": forecast['main']['temp'],
        "feels_like": forecast['main']['feels_like'],
        "temp_min": forecast['main']['temp_min'],
        "temp_max": forecast['main']['temp_max'],
        "pressure": forecast['main']['pressure'],
        "humidity": forecast['main']['humidity'],

        # weather description
        "weather_main": forecast['weather'][0]['main'],
        "weather_description": forecast['weather'][0]['description'],
        "weather_icon": forecast['weather'][0]['icon'],

        # extra information
        "clouds": forecast['clouds']['all'],
        "wind_speed": forecast['wind']['speed'],
        "wind_deg": forecast['wind']['deg'],
        "wind_gust": forecast['wind'].get('gust'),
        "visibility": forecast['visibility'],
        "rain_probability": forecast['pop'],
    }

    return render(request, "dashboard.html", sendings)