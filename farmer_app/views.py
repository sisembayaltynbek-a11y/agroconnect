from decimal import Decimal
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

from .models import Deliveries, Products, Categories, Farmer, Feedback
from .forms import AddFarmProduct, FarmerSignUpForm

from django.views.generic import DeleteView, UpdateView

class Index(View):
    API_KEY = "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"
    template_name = "home.html"

    def get(self, request):
        categories = Categories.objects.all()
        cheap_products = Products.objects.filter(price__lt=Decimal('500.00'))[:8]
        popular_products = Products.objects.all().order_by('-id')[:8] 
        staged_deliveries = Deliveries.objects.filter(working_stage__gte=3)
        
        return render(request, self.template_name, {
            'categories': categories,
            'deliveries': staged_deliveries,
            'popular_products': popular_products,
            'cheap_products': cheap_products,  # Renamed for clarity
            'ai_response': None,
        })
    
    def post(self, request):
        user_input = request.POST.get("user_input", "")
        ai_response = self.get_response(user_input)
        categories = Categories.objects.all()
        staged_deliveries = Deliveries.objects.filter(working_stage__gte=3)
        cheap_products = Products.objects.filter(price__lt=Decimal('500.00'))[:8]
        popular_products = Products.objects.all().order_by('-id')[:8]
        
        return render(request, self.template_name, {
            'categories': categories,
            'deliveries': staged_deliveries,
            'popular_products': popular_products,
            'cheap_products': cheap_products,
            'ai_response': ai_response,
            'user_input': user_input,
        })

    
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
            model="deepseek/deepseek-r1-0528:free",
            messages=[
                {
                "role": "user",
                "content": f"I have a farm website and a user please this is the question of my websites user: {user_input}"
                }
                ]
            )
            print(completion.choices[0].message.content)
        except:
            return "try again!"
                
        print(completion.choices[0].message.content)
        return str(completion.choices[0].message.content)
    

def category_products(request, id):
    category = get_object_or_404(Categories, id=id)
    products = Products.objects.filter(category=category)
    return render(request, 'category.html', {
        'category': category,
        'products': products
    })


class AddProductView(LoginRequiredMixin, CreateView):
    model = Products
    form_class = AddFarmProduct
    template_name = 'sell.html'
    success_url = reverse_lazy('home')

    def form_valid(self, form):
        farmer, _ = Farmer.objects.get_or_create(
            user=self.request.user,
            defaults={
                'name': self.request.user.username,
                'phonenumber': 'Not provided'
            }
        )
        form.instance.farmer = farmer
        return super().form_valid(form)


class Login(LoginView):
    template_name = 'account/login.html'

    def get_success_url(self):
        return reverse_lazy('home')

from django.contrib.auth import login
from django.contrib.auth import authenticate  # Add this import

class FarmerSignUpView(FormView):
    template_name = 'account/signup.html'
    form_class = FarmerSignUpForm
    success_url = reverse_lazy('home')

    @transaction.atomic
    def form_valid(self, form):
        # Create user
        user = User.objects.create_user(
            username=form.cleaned_data['username'],
            email=form.cleaned_data['email'],
            password=form.cleaned_data['password1'],
        )

        # Create farmer profile
        Farmer.objects.create(
            user=user,
            name=form.cleaned_data['name'],
            phonenumber=form.cleaned_data['phonenumber'],
            address=form.cleaned_data.get('address', '')
        )

        # First authenticate the user
        user = authenticate(
            username=form.cleaned_data['username'],
            password=form.cleaned_data['password1']
        )
        
        # Then log them in
        if user is not None:
            login(self.request, user)
        else:
            # If authentication fails, still redirect but show a message
            messages.warning(self.request, "Account created but automatic login failed. Please log in manually.")
        
        return redirect(self.success_url)
    
class Logout(LogoutView):
    template_name = 'account/logout.html'


def products(request):
    products_list = Products.objects.all()
    return render(request, 'products.html', {
        'products': products_list,
        'categories': Categories.objects.all()
    })

@login_required
def product_details(request, slug):
    product = get_object_or_404(Products, slug=slug)
    feedbacks = product.received_feedbacks.select_related('farmer').order_by('-created_at')

    can_give_feedback = False

    if request.user.is_authenticated:
        try:
            farmer = request.user.farmer
            can_give_feedback = not Feedback.objects.filter(
                farmer=farmer,
                product=product
            ).exists()
        except Farmer.DoesNotExist:
            farmer = None

        if request.method == "POST" and can_give_feedback:
            rating = int(request.POST.get("rating"))
            comment = request.POST.get("comment")

            Feedback.objects.create(
                farmer=farmer,
                product=product,
                rating=rating,
                comment=comment
            )
            messages.success(request, "Thank you for your feedback!")
            return redirect("product-details", slug=product.slug)

    return render(request, "product_details.html", {
        "product": product,
        "feedbacks": feedbacks,
        "can_give_feedback": can_give_feedback,
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
        item['id'] = pid
        item['price'] = price  # Update with float value
        item['total'] = price * item['qty']
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
    cart = request.session.get('cart', {})
    pid = str(product.id)  # Use string as key for consistency
    
    if pid in cart:
        cart[pid]['qty'] += 1
    else:
        cart[pid] = {
            'name': product.name,
            'price': float(product.price),  # Ensure price is stored as float
            'qty': 1,
        }
    
    request.session['cart'] = cart
    messages.success(request, f"{product.name} added to cart")
    return redirect(request.META.get('HTTP_REFERER', 'products'))

@login_required
@require_POST
def toggle_like(request, product_id):
    product = get_object_or_404(Products, id=product_id)
    farmer = request.user.farmer

    if product in farmer.liked_products.all():
        farmer.liked_products.remove(product)
    else:
        farmer.liked_products.add(product)

    return redirect(request.META.get('HTTP_REFERER', 'products'))


# ADD THIS FUNCTION-BASED VIEW FOR DELETING CART ITEMS
@login_required
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

@login_required
def profile(request):
    try:
        farmer = Farmer.objects.get(user=request.user)
        products = Products.objects.filter(farmer=farmer)

        context = {
            'farmer': farmer,
            'products': products,
        }
        
        return render(request, 'profile.html', context)
    
    except Farmer.DoesNotExist:
        return render(request, 'error.html', {'message': 'Farmer profile not found'})    

@login_required
def delete_self_published(request, product_id):
    try:
        farmer = Farmer.objects.get(user=request.user)
        product = get_object_or_404(Products, id=product_id)

        if product.farmer != farmer:
            messages.error(request, "You can only delete your own products!")
            return redirect('profile')
        
        product_name = product.name
        product.delete()
        
        messages.success(request, f"Product '{product_name}' has been deleted successfully!")
    
    except Products.DoesNotExist:
        messages.error(request, "Product not found!")
    
    return redirect('profile') 