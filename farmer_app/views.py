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
import re

from .models import Buyer, Deliveries, Location, Order, Products, Categories, Farmer, Feedback, CarDetails, ChatHistory
from .forms import AddFarmProduct, BuyerSignUpForm, FarmerSignUpForm, DeliverySignUpForm
from django.utils.decorators import method_decorator

from django.views.generic import DeleteView, UpdateView
from django.db.models import Avg

import base64
import os
import random
import stripe
from django.conf import settings
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.urls import reverse


from django.contrib.auth.mixins import LoginRequiredMixin  # optional — see below

class Index(View):
    ai_model = "llama3"
    template_name = "home.html"

    def get(self, request):
        user = request.user
        greeting = f"Сәлем, {user.username if user.is_authenticated else 'Қонақ'}!"

        context = {
            'greeting': greeting,
            'personal_tip': "Бүгін Алматы маңында арзан көкөністер көп — бағаларды тексеріңіз!",  # fallback or cache later
            'categories': Categories.objects.all(),
            'deliveries': Deliveries.objects.filter(working_stage__gte=3),
            'popular_products': Products.objects.all().order_by('-id')[:8],
            'cheap_products': Products.objects.filter(price__lt=Decimal('5000.00'))[:8],
            'ai_response': None,
        }
        return render(request, self.template_name, context)

    def post(self, request):
        user_input = request.POST.get("user_input", "").strip()
        user = request.user

        greeting = f"Сәлем, {user.username if user.is_authenticated else 'Қонақ'}!"

        # Optional: only generate tip if user is logged in
        personal_tip = "AI кеңесі қолжетімсіз"
        if user.is_authenticated:
            # You can make this more personal later (e.g. include city, likes)
            tip_prompt = (
                f"User is from Almaty, Kazakhstan. "
                f"Give one short, practical sentence about cheap/seasonal products "
                f"they can buy today in their region. "
                f"Example: Алматы маңында бүгін алма өніміне сұраныс жоғары — бағаны тексеріңіз!"
            )
            personal_tip = self.get_response(tip_prompt)

        ai_response = None
        if user_input:
            ai_response = self.get_response(user_input)

        context = {
            'greeting': greeting,
            'personal_tip': personal_tip,
            'categories': Categories.objects.all(),
            'deliveries': Deliveries.objects.filter(working_stage__gte=3),
            'popular_products': Products.objects.all().order_by('-id')[:8],
            'cheap_products': Products.objects.filter(price__lt=Decimal('5000.00'))[:8],
            'ai_response': ai_response,
            'user_input': user_input,
        }
        return render(request, self.template_name, context)

    def get_response(self, user_input):
        try:
            buyer = getattr(self.request.user, "buyer", None) if self.request.user.is_authenticated else None

            response = requests.post(
                "http://localhost:11434/api/chat",
                json={
                    "model": self.ai_model,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are AgriConnect AI — practical agricultural expert for Kazakhstan. "
                                "Answer with real facts and don't lie."
                            )
                        },
                        {"role": "user", "content": user_input}
                    ],
                    "stream": False
                },
                timeout=60
            )

            if response.status_code == 200:
                data = response.json()
                content = data["message"]["content"]
                if buyer:
                    ChatHistory.objects.create(
                        buyer=buyer,
                        prompt=user_input,
                        result=content,
                    )
                return content
            else:
                print("Ollama error:", response.text)
                return "AI қазір қолжетімсіз"

        except Exception as e:
            print("Error in get_response:", e)
            return "Қателік шықты, қайта көріңіз"
        

def ai_detector(request, product_id):
    product = get_object_or_404(Products, id=product_id)
    response_text = None

    try:
        # ✅ Check if image exists
        if not product.image:
            response_text = "No image available for this product."
            return render(request, "product_details.html", {
                "product": product,
                "response": response_text
            })

        image_path = product.image.path

        # ✅ Convert image to base64
        with open(image_path, "rb") as img:
            image_base64 = base64.b64encode(img.read()).decode("utf-8")

        # ✅ Call Ollama
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llava",
                "prompt": "Analyze this plant image. Identify possible disease and suggest treatment.",
                "images": [image_base64],
                "stream": False
            },
            timeout=90
        )

        print("STATUS:", response.status_code)

        if response.status_code == 200:
            data = response.json()

            # ✅ Correct parsing for Ollama generate
            response_text = data.get("response", "No response from AI")
        else:
            response_text = "AI error"

    except Exception as e:
        print("ERROR:", e)
        response_text = "Disease detection unavailable"

    return render(request, "product_details.html", {
        "product": product,
        "response": response_text
    })

def category_products(request, id):
    category = get_object_or_404(Categories, id=id)
    products = Products.objects.filter(category=category)
    return render(request, 'category.html', {
        'category': category,
        'products': products
    })

from django.http import JsonResponse
import requests

def ai_price_advisor(request, product_name):
    try:
        response = requests.post(
            "http://localhost:11434/api/chat",
            json={
                "model": "llama3",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an expert in Kazakhstan agricultural markets. Return ONLY a number in KZT."
                    },
                    {
                        "role": "user",
                        "content": f"Suggest a reasonable market price for {product_name} in Kazakhstan farm markets."
                    }
                ],
                "stream": False
            },
            timeout=60
        )

        if response.status_code == 200:
            data = response.json()
            suggestion = data["message"]["content"]
        else:
            suggestion = "Unavailable"

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

        buyer, created = Buyer.objects.get_or_create(user=self.request.user)

        if not buyer:
            messages.error(self.request, "You need a buyer account first.")
            return redirect("home")

        if Deliveries.objects.filter(buyer=buyer).exists():
            messages.error(self.request, "You are already a delivery person.")
            return redirect("profile")

        if Farmer.objects.filter(buyer=buyer).exists():
            messages.error(self.request, "You are already a farmer.")
            return redirect("profile")

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
            brand=buyer.user.username,
            phonenumber=form.cleaned_data["phonenumber"],
            address=form.cleaned_data["address"],
            location=location,
            license=form.cleaned_data["license"]
        )

        messages.success(self.request, "You are now a farmer!")

        return redirect(self.success_url)
            
class BecomeDeliveryView(LoginRequiredMixin, FormView):
    template_name = "account/become_delivery.html"
    form_class = DeliverySignUpForm
    success_url = reverse_lazy("profile")

    def form_valid(self, form):
        buyer, created = Buyer.objects.get_or_create(user=self.request.user)
        index = Index()

        if Farmer.objects.filter(buyer=buyer).exists():
            messages.error(self.request, "You are already a farmer.")
            return redirect("profile")

        if Deliveries.objects.filter(buyer=buyer).exists():
            messages.error(self.request, "You are already a delivery person.")
            return redirect("profile")

        car = CarDetails.objects.create(
            carname=form.cleaned_data["carname"],
            carnumber=form.cleaned_data["carnumber"],
            vehicle_registration=form.cleaned_data["vehicle_registration"],
            insurance=form.cleaned_data["insurance"],
            medical_certificate=form.cleaned_data["medical_certificate"],
        )

        Deliveries.objects.create(
            buyer=buyer,
            vehicle=car,
            fullname=buyer.user.username,
            working_stage=int(form.cleaned_data["working_stage"]),
            recommendation=index.get_response('give recommendation for delivery')
        )

        messages.success(self.request, "You are now a delivery driver! 🚚")
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

# @login_required
# def create_checkout_session(request):
#     cart = request.session.get('cart', {})
#     if not cart:
#         return redirect('cart')

#     available_deliveries = Deliveries.objects.all()
#     if available_deliveries.exists():
#         selected_delivery = random.choice(available_deliveries)
#         request.session['assigned_delivery_id'] = selected_delivery.id
    
#     DELIVERY_FEE_KZT = 500 
    
#     line_items = []
    
#     for pid, item in cart.items():
#         unit_amount = int(float(item['price']) * 100)
#         line_items.append({
#             'price_data': {
#                 'currency': 'kzt',
#                 'product_data': {'name': item['name']},
#                 'unit_amount': unit_amount,
#             },
#             'quantity': item['qty'],
#         })

#     line_items.append({
#         'price_data': {
#             'currency': 'kzt',
#             'product_data': {
#                 'name': 'Delivery Fee',
#                 'description': 'Flat rate shipping to your location',
#             },
#             'unit_amount': DELIVERY_FEE_KZT * 100,
#         },
#         'quantity': 1,
#     })

#     try:
#         checkout_session = stripe.checkout.Session.create(
#             payment_method_types=['card'],
#             line_items=line_items,
#             mode='payment',
#             success_url=request.build_absolute_uri(reverse('payment_success')),
#             cancel_url=request.build_absolute_uri(reverse('cart')),
#         )
#         return redirect(checkout_session.url, code=303)
#     except Exception as e:
#         return render(request, 'error.html', {'error': str(e)})

@login_required
def create_checkout_session(request):
    cart = request.session.get('cart', {})
    if not cart:
        return redirect('cart')

    # Assign a delivery person randomly if available
    available_deliveries = Deliveries.objects.all()
    buyer = getattr(request.user, "buyer", None)
    delivery = getattr(buyer, "deliveries", None)
    listof_deliveries = []
    selected_delivery = None
    if available_deliveries.exists():
        for i in available_deliveries:
            if i !=delivery:
                listof_deliveries.append(i)
            else:
                pass
    
    if listof_deliveries:
        selected_delivery = random.choice(listof_deliveries)
        request.session['assigned_delivery_id'] = selected_delivery.id
    
    DELIVERY_FEE_KZT = 500  # flat delivery fee

    line_items = []
    subtotal = 0

    for pid, item in cart.items():
        price = float(item['price'])
        qty = int(item.get('qty', 1))
        subtotal += price * qty

        line_items.append({
            'price_data': {
                'currency': 'kzt',
                'product_data': {'name': item['name']},
                'unit_amount': int(price * 100),
            },
            'quantity': qty,
        })

    # Add delivery fee
    line_items.append({
        'price_data': {
            'currency': 'kzt',
            'product_data': {
                'name': 'Delivery Fee',
                'description': 'Flat rate shipping',
            },
            'unit_amount': DELIVERY_FEE_KZT * 100,
        },
        'quantity': 1,
    })

    total_price = subtotal + DELIVERY_FEE_KZT

    # Save Order in DB
    
    if buyer and selected_delivery:
        Order.objects.create(
            buyer=buyer,
            delivery=selected_delivery,
            total_price=total_price
        )

    # Create Stripe session
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
        try:
            delivery_person = Deliveries.objects.get(id=delivery_id)
        except Deliveries.DoesNotExist:
            delivery_person = None

    if 'cart' in request.session:
        del request.session['cart']

    buyer = getattr(request.user, "buyer", None)
    latest_order = None
    if buyer:
        latest_order = Order.objects.filter(buyer=buyer).order_by('-created_at').first()

    return render(request, 'success.html', {
        'delivery_person': delivery_person,
        'order': latest_order
    })

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
            "delivery": None,
            "products": [],
            "orders": [],
        })

    farmer = getattr(buyer, "farmer", None)
    delivery = getattr(buyer, "deliveries", None)
    history = ChatHistory.objects.filter(buyer=buyer).order_by('-time')[:4]
    products = Products.objects.filter(farmer=farmer) if farmer else []
    orders = Order.objects.filter(delivery=delivery) if delivery else []
    my_orders = Order.objects.filter(delivery=delivery) if delivery else []

    return render(request, "profile.html", {
        "buyer": buyer,
        "farmer": farmer,
        "delivery": delivery,
        "history":history,
        "products": products,
        "orders": orders,
        "my_orders":my_orders,
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
    delivery = getattr(buyer, "deliveries", None)
    return render(request, 'choice.html', {
        'buyer': buyer,
        'farmer': farmer,
        'delivery':delivery,
    })

class UpdatePost(LoginRequiredMixin, UpdateView):
    model = Products
    fields = ['image', 'name', 'price', 'excerpt', 'description', 'category']
    template_name = 'update.html'
    success_url = reverse_lazy('products')
    def get_queryset(self):
        buyer = getattr(self.request.user, "buyer", None)
        farmer = getattr(buyer, "farmer", None)
        delivery = getattr(buyer, "deliveries", None)
        if farmer:
            return Products.objects.filter(farmer=farmer)
        return Products.objects.none()

class UpdateBuyer(LoginRequiredMixin, UpdateView):
    model = Buyer
    fields = ['name', 'avatar']
    template_name = 'update_buyer.html'
    success_url = reverse_lazy('profile')  # redirect after success

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
        try:
            response = requests.post(
                "http://localhost:11434/api/chat",
                json={
                    "model": "llama3",
                    "messages": [
                        {
                            "role": "system",
                            "content": "Return ONLY coordinates like: 43.2220,76.8512"
                        },
                        {
                            "role": "user",
                            "content": f"Give only latitude and longitude without words for this location: {location_name}"
                        }
                    ],
                    "stream": False
                },
                timeout=60
            )

            if response.status_code == 200:
                data = response.json()
                return data["message"]["content"].split(",")

            return ["43.2220", "76.8512"]

        except Exception as e:
            print(e)
            return ["43.2220", "76.8512"]
    
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

class DeliveryUpdateView(LoginRequiredMixin, UpdateView):
    model = Deliveries
    fields = ['fullname', 'working_stage', 'image']
    template_name = "update_delivery.html"
    success_url = reverse_lazy('profile')

    def get_object(self, queryset=None):
        buyer = getattr(self.request.user, "buyer", None)
        if not buyer:
            return None
        delivery = getattr(buyer, "deliveries", None)
        return delivery

    def form_valid(self, form):
        self.object = form.save(commit=False)

        car = self.object.vehicle
        car.carname = self.request.POST.get("carname", car.carname)
        car.carnumber = self.request.POST.get("carnumber", car.carnumber)

        if "vehicle_registration" in self.request.FILES:
            car.vehicle_registration = self.request.FILES["vehicle_registration"]
        if "insurance" in self.request.FILES:
            car.insurance = self.request.FILES["insurance"]
        if "medical_certificate" in self.request.FILES:
            car.medical_certificate = self.request.FILES["medical_certificate"]

        car.save()
        self.object.save()

        messages.success(self.request, "Delivery profile updated successfully!")
        return redirect(self.success_url)

def iot_dashboard(request):
    city_name = request.POST.get("city_name") or request.GET.get("city_name") or "Almaty"
    product_name = request.POST.get("product") or request.GET.get("product") or "Apple"
    product_name = product_name.strip()

    # ──────────────────────────────
    # WEATHER DATA
    # ──────────────────────────────
    weather_labels = []
    weather_temps = []
    weather_humidity = []

    try:
        url = f"https://api.openweathermap.org/data/2.5/forecast?q={city_name}&appid=89c57e8dfcd68a00c8b51ce244feff28&units=metric"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        forecast_list = data["list"][:8]  # next 24h
        forecast = forecast_list[0]

        for item in forecast_list:
            weather_labels.append(item.get("dt_txt")[11:16])  # HH:MM format
            weather_temps.append(item["main"].get("temp"))
            weather_humidity.append(item["main"].get("humidity"))

        weather = {
            "city": city_name,
            "datetime": forecast.get('dt_txt'),
            "temp": forecast['main'].get('temp'),
            "feels_like": forecast['main'].get('feels_like'),
            "temp_min": forecast['main'].get('temp_min'),
            "temp_max": forecast['main'].get('temp_max'),
            "pressure": forecast['main'].get('pressure'),
            "humidity": forecast['main'].get('humidity'),
            "weather_main": forecast['weather'][0].get('main'),
            "weather_description": forecast['weather'][0].get('description'),
            "weather_icon": forecast['weather'][0].get('icon'),
            "clouds": forecast.get('clouds', {}).get('all'),
            "wind_speed": forecast.get('wind', {}).get('speed'),
            "wind_deg": forecast.get('wind', {}).get('deg'),
            "wind_gust": forecast.get('wind', {}).get('gust'),
            "visibility": forecast.get('visibility'),
            "rain_probability": forecast.get('pop', 0),
        }

    except Exception as e:
        print("Weather error:", e)
        weather = {"city": city_name}

    # ──────────────────────────────
    # AI PRODUCT TIPS
    # ──────────────────────────────
    advice = "AI advice unavailable."
    try:
        prompt_tips = f"""
You are an expert agronomist in Kazakhstan.
Farmer is near {city_name}.
Product: {product_name}.
Give 3 short practical tips for the farmer regarding this product.
"""
        r = requests.post(
            "http://localhost:11434/api/chat",
            json={"model": "llama3", "messages":[{"role":"user","content":prompt_tips}], "stream": False},
            timeout=60
        )
        data = r.json()
        advice = data.get("message", {}).get("content", advice)
    except Exception as e:
        print("AI Tips error:", e)

    chart_labels = []
    chart_prices = []
    try:
        # Separate AI prompt just for generating graph numbers
        prompt_graph = f"""
You are an agricultural market expert in Kazakhstan.
Product: {product_name}.
Location: {city_name}.

Please give 6 predicted numbers (e.g., prices, sales, demand) for this product in the next days.
Return only numbers separated by commas.
"""
        r = requests.post(
            "http://localhost:11434/api/chat",
            json={"model":"llama3", "messages":[{"role":"user","content":prompt_graph}], "stream":False},
            timeout=60
        )
        data = r.json()
        graph_response = data.get("message", {}).get("content", "")

        numbers = re.findall(r'\d+', graph_response)
        numbers = numbers[:6]  # take first 6 numbers
        chart_prices = [int(n) for n in numbers]
        chart_labels = [f"Day {i+1}" for i in range(len(chart_prices))]

    except Exception as e:
        print("AI Graph error:", e)

    # ──────────────────────────────
    # CONTEXT
    # ──────────────────────────────
    context = {
        **weather,
        "advice": advice,
        "product": product_name,

        # WEATHER CHART
        "weather_chart_labels": weather_labels,
        "weather_chart_temps": weather_temps,
        "weather_chart_humidity": weather_humidity,

        # AI PRODUCT CHART
        "chart_labels": chart_labels,
        "chart_prices": chart_prices,
    }

    return render(request, "dashboard.html", context)