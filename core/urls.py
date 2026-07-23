from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # === АУТЕНТИФИКАЦИЯ ===
    path('auth/login/', views.login_view, name='login'),
    path('auth/enter-code/', views.enter_code_view, name='enter_code'),
    path('auth/enter-name/', views.enter_name_view, name='enter_name'),
    path('auth/choose-role/', views.choose_role_view, name='choose_role'),
    path('auth/logout/', views.logout_view, name='logout'),
    
    # === ГЛАВНЫЕ СТРАНИЦЫ ===
    path('', views.home_view, name='home'),
    path('profile/', views.profile_view, name='profile'),
    path('owner/dashboard/', views.owner_restaurants_view, name='owner_dashboard'),    path('restaurant/<slug:slug>/', views.restaurant_detail_view, name='restaurant_detail'),
 
    # Бронирование
    path('restaurant/<slug:slug>/booking/', views.booking_form_view, name='booking_form'),
    path('restaurant/<slug:slug>/review/add/', views.add_review_view, name='add_review'),
    path('booking/success/<int:booking_id>/', views.booking_success_view, name='booking_success'),
    # 🆕 Избранное
    path('favorite/<slug:slug>/', views.toggle_favorite_view, name='toggle_favorite'),
    path('favorites/', views.favorites_view, name='favorites'),
    # 🆕 История заказов
    path('orders/', views.order_history_view, name='order_history'),
    path('orders/<int:booking_id>/', views.booking_detail_view, name='booking_detail'),
    path('orders/<int:booking_id>/cancel/', views.cancel_booking_view, name='cancel_booking'),
    # 🆕 Дашборд владельца
    path('owner/restaurants/', views.owner_restaurants_view, name='owner_restaurants'),
    path('owner/restaurants/add/', views.add_restaurant_view, name='add_restaurant'),
    path('owner/restaurants/<slug:slug>/edit/', views.edit_restaurant_view, name='edit_restaurant'), # 🆕 НОВОЕ
    path('owner/analytics/<slug:slug>/', views.restaurant_analytics_view, name='restaurant_analytics'),
]