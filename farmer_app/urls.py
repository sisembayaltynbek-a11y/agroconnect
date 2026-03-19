from django.urls import path
from . import views

urlpatterns = [
    path('', views.Index.as_view(), name='home'),
    
    path('accounts/login/', views.Login.as_view(), name='login'),
    path('accounts/logout/', views.Logout.as_view(), name='logout'),
    path('accounts/signup/', views.BuyerSignUpView.as_view(), name='signup'),
    path('accounts/become-farmer/', views.BecomeFarmerView.as_view(), name='become-farmer'),
    path('accounts/become-delivery/', views.BecomeDeliveryView.as_view(), name='become-delivery'),
    
    path('suggest-price/<str:product_name>/', views.ai_price_advisor, name='suggest-price'),
    path("detection/<int:product_id>/", views.ai_detector, name="detection"),
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
    path('cart/increase/<int:product_id>/', views.increase_quantity, name='increase'),
    path('like/<int:product_id>/', views.toggle_like, name='toggle-like'),
    path('cart/delete/<int:pk>/', views.delete_cart_item, name='delete-cart-item'),

    path('profile/', views.profile, name='profile'),
    path('choice/', views.choose_page, name='choice'),
    path('product/delete/<int:product_id>/', views.delete_self_published, name='delete_product'),
    path('posts/update/<int:pk>/', views.UpdatePost.as_view(), name="update-page"),
    path('posts/buyer_update/<int:pk>/', views.UpdateBuyer.as_view(), name="update-page-buyer"),
    path('posts/farmer_update/<int:pk>/', views.UpdateFarmer.as_view(), name="update-page-farmer"),

    path('dashboard/', views.iot_dashboard, name='dashboard'),

    path('checkout/', views.create_checkout_session, name='create_checkout_session'),
    path('success/', views.payment_success, name='payment_success'),
    path('subsidy-kaz/', views.subsidy_page, name='subsidy')
]