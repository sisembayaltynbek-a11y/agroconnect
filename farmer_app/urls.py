from django.urls import path
from . import views

urlpatterns = [
    path('', views.Index.as_view(), name='home'),
    
    path('accounts/login/', views.Login.as_view(), name='login'),
    path('accounts/logout/', views.Logout.as_view(), name='logout'),
    path('accounts/signup/', views.FarmerSignUpView.as_view(), name='signup'),
    
    path('add-product/', views.AddProductView.as_view(), name='add-product'),
    path('products/', views.products, name='products'),
    path(
        "products/<slug:slug>/",
        views.product_details,
        name="product-details"
    ),
    path('search/', views.search, name='search'),
    path('category/<int:id>/', views.category_products, name='category'),
    
    # Cart URLs - USE FUNCTION-BASED VIEW
    path('cart/', views.cart, name='cart'),
    path('cart/add/<int:product_id>/', views.add_to_cart, name='add-to-cart'),
    path('like/<int:product_id>/', views.toggle_like, name='toggle-like'),
    path('cart/delete/<int:pk>/', views.delete_cart_item, name='delete-cart-item'),

    path('profile/', views.profile, name='profile'),
    path('product/delete/<int:product_id>/', views.delete_self_published, name='delete_product'),
]