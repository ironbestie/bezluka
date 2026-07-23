from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from datetime import datetime
from django.conf import settings

# ⚠️ ВАЖНО: Импортируем ВСЕ необходимые модели здесь
from .models import (
    GuestProfile, OwnerProfile, VerificationCode, LoyaltyTransaction,
    Restaurant, StaffMember, Menu, Review, Booking
)
from .sms_service import generate_code, send_sms_code


# ==========================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==========================================
def get_client_ip(request):
    """Получить IP-адрес пользователя"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0]
    return request.META.get('REMOTE_ADDR')


# ==========================================
# 1. ВВОД ТЕЛЕФОНА
# ==========================================
def login_view(request):
    """Первый экран: ввод номера телефона"""
    if request.user.is_authenticated:
        if hasattr(request.user, 'owner_profile'):
            return redirect('core:owner_dashboard')
        elif hasattr(request.user, 'guest_profile'):
            return redirect('core:home')
        else:
            return redirect('core:choose_role')
    
    if request.method == 'POST':
        phone = request.POST.get('phone', '').strip()
        
        if not phone:
            messages.error(request, 'Введите номер телефона')
            return render(request, 'auth/login.html')
        
        # Очистка номера для SMS.ru (приведение к формату 11 цифр с 7ХХХХХХХХХХ)
        clean_phone = ''.join(filter(str.isdigit, phone)) # Оставляем только цифры
        
        if clean_phone.startswith('8') and len(clean_phone) == 11:
            clean_phone = '7' + clean_phone[1:] # Меняем 8 на 7
        elif clean_phone.startswith('7') and len(clean_phone) == 11:
            pass # Оставляем как есть
        else:
            messages.error(request, 'Введите корректный номер из 11 цифр (например, 89991234567)')
            return render(request, 'auth/login.html')
        
        # Защита от спама: не чаще 1 SMS в минуту на один номер
        recent_codes = VerificationCode.objects.filter(
            phone=clean_phone,
            created_at__gte=timezone.now() - timedelta(minutes=1)
        ).count()
        
        if recent_codes > 0:
            messages.error(request, 'Подождите 1 минуту перед повторным запросом')
            return render(request, 'auth/login.html')
        
        # === ИСПРАВЛЕНИЕ ДЕМО-РЕЖИМА ===
        api_id = getattr(settings, 'SMS_RU_API_ID', '')
        if api_id == 'SMS_RU_API_ID' or not api_id:
            # Если ключ не настроен, жестко задаем код 1234, чтобы он совпадал с подсказкой на экране
            code = '1234'
            print(f"\n{'='*50}")
            print(f"📱 ДЕМО-РЕЖИМ: SMS на {clean_phone}")
            print(f"🔐 Код подтверждения: {code}")
            print(f"{'='*50}\n")
        else:
            # Если ключ настроен, генерируем случайный код и отправляем реальное SMS
            code = generate_code(length=4)
            result = send_sms_code(clean_phone, code)
            if not result['success']:
                messages.error(request, f'Не удалось отправить SMS: {result["message"]}')
                return render(request, 'auth/login.html')
        
        # Сохраняем код в БД (теперь это гарантированно '1234' в демо-режиме)
        expires_at = timezone.now() + timedelta(minutes=5)
        verification = VerificationCode.objects.create(
            phone=clean_phone,
            code=code,
            expires_at=expires_at,
            ip_address=get_client_ip(request),
        )
        
        request.session['verification_id'] = verification.id
        return redirect('core:enter_code')
    
    return render(request, 'auth/login.html')


# ==========================================
# 2. ВВОД КОДА
# ==========================================
def enter_code_view(request):
    """Второй экран: ввод кода подтверждения"""
    if request.user.is_authenticated:
        if hasattr(request.user, 'owner_profile'):
            return redirect('core:owner_dashboard')
        return redirect('core:home')
    
    verification_id = request.session.get('verification_id')
    if not verification_id:
        return redirect('core:login')
    
    try:
        verification = VerificationCode.objects.get(id=verification_id)
    except VerificationCode.DoesNotExist:
        return redirect('core:login')
    
    if request.method == 'POST':
        code = request.POST.get('code', '').strip()
        
        # Проверяем валидность кода
        if not verification.is_valid:
            if verification.is_expired:
                messages.error(request, 'Код истёк. Запросите новый.')
            elif verification.attempts >= 5:
                messages.error(request, 'Слишком много попыток. Запросите новый код.')
            return render(request, 'auth/enter_code.html', {'phone': verification.phone})
        
        # Проверяем совпадение
        if code == verification.code:
            # Код верный! Помечаем как использованный
            verification.is_used = True
            verification.save()
            
            # Очищаем сессию
            if 'verification_id' in request.session:
                del request.session['verification_id']
            
            # Ищем или создаём пользователя
            user, created = User.objects.get_or_create(
                username=verification.phone,
                defaults={'first_name': '', 'last_name': ''}
            )
            
            # Если новый — отправляем на ввод имени
            if created or not user.first_name:
                user.backend = 'django.contrib.auth.backends.ModelBackend'
                login(request, user)
                return redirect('core:enter_name')
            
            # Если существующий — сразу в систему
            user.backend = 'django.contrib.auth.backends.ModelBackend'
            login(request, user)
            
            if hasattr(user, 'owner_profile'):
                return redirect('core:owner_dashboard')
            return redirect('core:home')
        else:
            # Неверный код — увеличиваем счётчик попыток
            verification.attempts += 1
            verification.save()
            
            remaining_attempts = 5 - verification.attempts
            if remaining_attempts > 0:
                messages.error(request, f'Код введён неверно. Осталось попыток: {remaining_attempts}')
            else:
                messages.error(request, 'Слишком много попыток. Запросите новый код.')
    
    return render(request, 'auth/enter_code.html', {'phone': verification.phone})


# ==========================================
# 3. ВВОД ИМЕНИ
# ==========================================
def enter_name_view(request):
    """Третий экран: как вас зовут?"""
    if not request.user.is_authenticated:
        return redirect('core:login')
    
    if request.user.first_name:
        return redirect('core:choose_role')
    
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        
        if not first_name:
            messages.error(request, 'Введите имя')
            return render(request, 'auth/enter_name.html')
        
        request.user.first_name = first_name
        request.user.last_name = last_name
        request.user.save()
        
        return redirect('core:choose_role')
    
    return render(request, 'auth/enter_name.html')


# ==========================================
# 4. ВЫБОР РОЛИ
# ==========================================
def choose_role_view(request):
    """Четвёртый экран: выберите роль"""
    if not request.user.is_authenticated:
        return redirect('core:login')
    
    if hasattr(request.user, 'guest_profile') or hasattr(request.user, 'owner_profile'):
        if hasattr(request.user, 'owner_profile'):
            return redirect('core:owner_dashboard')
        return redirect('core:home')
    
    if request.method == 'POST':
        role = request.POST.get('role')
        
        if role == 'guest':
            GuestProfile.objects.create(
                user=request.user,
                phone=request.user.username,
                points_balance=500,
                cashback_percent=2,
                loyalty_level='Select',
            )
            
            LoyaltyTransaction.objects.create(
                user=request.user,
                points_change=500,
                reason='registration',
                description='Приветственные баллы за регистрацию',
            )
            
            return redirect('core:home')
        
        elif role == 'owner':
            OwnerProfile.objects.create(user=request.user)
            return redirect('core:owner_dashboard')
    
    return render(request, 'auth/choose_role.html')


# ==========================================
# 5. ВЫХОД
# ==========================================
def logout_view(request):
    logout(request)
    return redirect('core:login')


# ==========================================
# ГЛАВНАЯ СТРАНИЦА
# ==========================================
@login_required
def home_view(request):
    if hasattr(request.user, 'owner_profile'):
        return redirect('core:owner_dashboard')
    
    if not hasattr(request.user, 'guest_profile'):
        return redirect('core:choose_role')
    
    restaurants = Restaurant.objects.filter(is_active=True).order_by('name')
    
    # 👇 НОВОЕ: Получаем список избранных ресторанов пользователя
    user_favorites = Restaurant.objects.filter(
        favorited_by__user=request.user
    )
    
    context = {
        'guest_profile': request.user.guest_profile,
        'restaurants': restaurants,
        'user_favorites': user_favorites,  # 👈 Передаём в шаблон
    }
    return render(request, 'home.html', context)


# ==========================================
# ДАШБОРД ВЛАДЕЛЬЦА
# ==========================================
@login_required
def owner_dashboard_view(request):
    """Старая функция — теперь редиректим на список ресторанов"""
    if not hasattr(request.user, 'owner_profile'):
        return redirect('core:home')
    return redirect('core:owner_restaurants')

@login_required
def restaurant_detail_view(request, slug):
    """Страница конкретного ресторана (полная версия)"""
    if not hasattr(request.user, 'guest_profile'):
        return redirect('core:owner_dashboard')
    
    restaurant = Restaurant.objects.get(slug=slug)
    staff = restaurant.staff.all()[:6]
    
    # Меню
    menu = restaurant.menus.filter(is_active=True).first()
    menu_categories = menu.categories.prefetch_related('items').all() if menu else []
    
    # Отзывы
    reviews = restaurant.reviews.filter(is_moderated=True).order_by('-created_at')[:3]
    
    # === РАСЧЕТ МЕТРИК ИЗ ОТЗЫВОВ (ВСЕГДА АКТУАЛЬНЫЕ) ===
    all_reviews = restaurant.reviews.filter(is_moderated=True)
    total_reviews = all_reviews.count() or 1
    
    # Общий рейтинг
    overall_rating = round(all_reviews.aggregate(avg=Avg('rating'))['avg'] or 0, 1)
    
    # Распределение оценок в процентах
    rating_counts = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
    for r in all_reviews.values('rating').annotate(count=Count('rating')):
        rating_counts[r['rating']] = r['count']
    
    rating_percentages = {
        5: round((rating_counts[5] / total_reviews) * 100),
        4: round((rating_counts[4] / total_reviews) * 100),
        3: round((rating_counts[3] / total_reviews) * 100),
        2: round((rating_counts[2] / total_reviews) * 100),
        1: round((rating_counts[1] / total_reviews) * 100),
    }
    
    # === МЕТРИКИ ПЕРСОНАЛА (пересчитываются из отзывов) ===
    if all_reviews.exists():
        staff_service_rating = round(all_reviews.aggregate(avg=Avg('service_rating'))['avg'] or 0, 1)
        staff_price_quality_rating = round(all_reviews.aggregate(avg=Avg('price_quality_rating'))['avg'] or 0, 1)
        staff_atmosphere_rating = round(all_reviews.aggregate(avg=Avg('atmosphere_rating'))['avg'] or 0, 1)
    else:
        staff_service_rating = 0
        staff_price_quality_rating = 0
        staff_atmosphere_rating = 0
    # ==================================================
    
    is_favorited = Favorite.objects.filter(user=request.user, restaurant=restaurant).exists()
    
    context = {
        'restaurant': restaurant,
        'staff': staff,
        'menu_categories': menu_categories,
        'reviews': reviews,
        'guest_profile': request.user.guest_profile,
        'is_favorited': is_favorited,
        'rating_percentages': rating_percentages,
        'total_reviews_count': total_reviews,
        'overall_rating': overall_rating,
        # Передаем рассчитанные метрики (не из модели!)
        'staff_service_rating': staff_service_rating,
        'staff_price_quality_rating': staff_price_quality_rating,
        'staff_atmosphere_rating': staff_atmosphere_rating,
    }
    return render(request, 'restaurant_detail.html', context)

from django.utils import timezone
from datetime import datetime


# ==========================================
# ФОРМА БРОНИРОВАНИЯ
# ==========================================
@login_required
def booking_form_view(request, slug):
    """Форма бронирования стола"""
    if not hasattr(request.user, 'guest_profile'):
        return redirect('core:owner_dashboard')
    
    restaurant = Restaurant.objects.get(slug=slug)
    guest_profile = request.user.guest_profile
    
    if request.method == 'POST':
        # Получаем данные из формы
        booking_date = request.POST.get('booking_date')
        booking_time = request.POST.get('booking_time')
        party_size = int(request.POST.get('party_size', 2))
        comment = request.POST.get('comment', '').strip()
        
        # Валидация
        if not booking_date or not booking_time:
            messages.error(request, 'Укажите дату и время')
            return render(request, 'booking_form.html', {'restaurant': restaurant})
        
        # Объединяем дату и время
        booking_datetime = datetime.strptime(f'{booking_date} {booking_time}', '%Y-%m-%d %H:%M')
        
        # Проверяем, что дата не в прошлом
        if booking_datetime < timezone.now():
            messages.error(request, 'Нельзя забронировать на прошедшее время')
            return render(request, 'booking_form.html', {'restaurant': restaurant})
        
        # Создаём бронь
        booking = Booking.objects.create(
            restaurant=restaurant,
            user=request.user,
            guest_name=f'{request.user.first_name} {request.user.last_name}'.strip(),
            guest_phone=request.user.username,
            party_size=party_size,
            booking_datetime=booking_datetime,
            comment=comment,
            source='bezluka_web',
            status='confirmed',  # Сразу подтверждаем
        )
        
        # === НАЧИСЛЕНИЕ КЭШБЭКА ===
        # Для демо считаем, что средний чек = avg_check ресторана * количество гостей
        estimated_amount = restaurant.avg_check * party_size
        
        # Кэшбэк зависит от репутации гостя (2-10%)
        cashback_percent = guest_profile.cashback_percent
        cashback_points = int(estimated_amount * cashback_percent / 100)
        
        # Начисляем баллы
        guest_profile.points_balance += cashback_points
        guest_profile.total_bookings += 1
        guest_profile.completed_bookings += 1
        guest_profile.total_spent += estimated_amount
        guest_profile.monthly_spent += estimated_amount
        guest_profile.save()
        
        # Обновляем репутацию и уровень
        guest_profile.calculate_reputation_and_cashback()
        
        # Создаём транзакцию лояльности
        LoyaltyTransaction.objects.create(
            user=request.user,
            points_change=cashback_points,
            reason='booking_cashback',
            related_booking=booking,
            description=f'Кэшбэк {cashback_percent}% за бронь в {restaurant.name}',
        )
        
        # Перенаправляем на страницу успеха
        return redirect('core:booking_success', booking_id=booking.id)
    
    context = {
        'restaurant': restaurant,
        'guest_profile': guest_profile,
    }
    return render(request, 'booking_form.html', context)


# ==========================================
# СТРАНИЦА УСПЕШНОГО БРОНИРОВАНИЯ
# ==========================================
@login_required
def booking_success_view(request, booking_id):
    """Страница подтверждения брони"""
    if not hasattr(request.user, 'guest_profile'):
        return redirect('core:owner_dashboard')
    
    booking = Booking.objects.get(id=booking_id, user=request.user)
    
    context = {
        'booking': booking,
        'guest_profile': request.user.guest_profile,
    }
    return render(request, 'booking_success.html', context)

# ==========================================
# ПРОФИЛЬ ГОСТЯ
# ==========================================
@login_required
def profile_view(request):
    """Страница профиля гостя"""
    if not hasattr(request.user, 'guest_profile'):
        return redirect('core:owner_dashboard')
    
    guest_profile = request.user.guest_profile
    recent_transactions = LoyaltyTransaction.objects.filter(user=request.user).order_by('-timestamp')[:5]
    
    context = {
        'guest_profile': guest_profile,
        'recent_transactions': recent_transactions,
    }
    return render(request, 'profile.html', context)


# ==========================================
# СТРАНИЦА РЕСТОРАНА
# ==========================================
@login_required
def restaurant_detail_view(request, slug):
    if not hasattr(request.user, 'guest_profile'):
        return redirect('core:owner_dashboard')
    
    restaurant = Restaurant.objects.get(slug=slug)
    staff = restaurant.staff.all()[:6]
    menus = restaurant.menus.filter(is_active=True).prefetch_related('categories', 'categories__items')
    reviews = restaurant.reviews.filter(is_moderated=True)[:3]
    
    # 👇 НОВОЕ: Проверяем, в избранном ли этот ресторан
    is_favorited = Favorite.objects.filter(user=request.user, restaurant=restaurant).exists()
    
    context = {
        'restaurant': restaurant,
        'staff': staff,
        'menus': menus,
        'reviews': reviews,
        'guest_profile': request.user.guest_profile,
        'is_favorited': is_favorited,  # 👈 Передаём в шаблон
    }
    return render(request, 'restaurant_detail.html', context)

# ==========================================
# ФОРМА БРОНИРОВАНИЯ
# ==========================================
@login_required
def booking_form_view(request, slug):
    """Форма бронирования стола"""
    if not hasattr(request.user, 'guest_profile'):
        return redirect('core:owner_dashboard')
    
    restaurant = Restaurant.objects.get(slug=slug)
    guest_profile = request.user.guest_profile
    
    if request.method == 'POST':
        booking_date = request.POST.get('booking_date')
        booking_time = request.POST.get('booking_time')
        party_size = int(request.POST.get('party_size', 2))
        comment = request.POST.get('comment', '').strip()
        
        if not booking_date or not booking_time:
            messages.error(request, 'Укажите дату и время')
            return render(request, 'booking_form.html', {'restaurant': restaurant, 'guest_profile': guest_profile})
        
        # 1. Создаем "наивную" дату и время из строки
        booking_datetime = datetime.strptime(f'{booking_date} {booking_time}', '%Y-%m-%d %H:%M')
        
        # 2. ⚠️ КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ: Делаем дату "осознанной" (добавляем часовой пояс из settings.py)
        booking_datetime = timezone.make_aware(booking_datetime)
        
        # 3. Теперь сравнение работает БЕЗ ОШИБОК!
        if booking_datetime < timezone.now():
            messages.error(request, 'Нельзя забронировать на прошедшее время')
            return render(request, 'booking_form.html', {'restaurant': restaurant, 'guest_profile': guest_profile})
        
        # Создаем бронь
        booking = Booking.objects.create(
            restaurant=restaurant,
            user=request.user,
            guest_name=f'{request.user.first_name} {request.user.last_name}'.strip(),
            guest_phone=request.user.username,
            party_size=party_size,
            booking_datetime=booking_datetime,
            comment=comment,
            source='bezluka_web',
            status='confirmed',
            amount=restaurant.avg_check * party_size,
        )
        
        # === НАЧИСЛЕНИЕ КЭШБЭКА ===
        estimated_amount = restaurant.avg_check * party_size
        cashback_percent = guest_profile.cashback_percent
        cashback_points = int(estimated_amount * cashback_percent / 100)
        
        guest_profile.points_balance += cashback_points
        guest_profile.total_bookings += 1
        guest_profile.completed_bookings += 1
        guest_profile.total_spent += estimated_amount
        guest_profile.monthly_spent += estimated_amount
        guest_profile.save()
        
        # Пересчитываем репутацию и уровень
        guest_profile.calculate_reputation_and_cashback()
        
        # Создаем запись в истории транзакций
        LoyaltyTransaction.objects.create(
            user=request.user,
            points_change=cashback_points,
            reason='booking_cashback',
            related_booking=booking,
            description=f'Кэшбэк {cashback_percent}% за бронь в {restaurant.name}',
        )
        
        return redirect('core:booking_success', booking_id=booking.id)
    
    context = {
        'restaurant': restaurant,
        'guest_profile': guest_profile,
    }
    return render(request, 'booking_form.html', context)
# ==========================================
# СТРАНИЦА УСПЕШНОГО БРОНИРОВАНИЯ
# ==========================================
@login_required
def booking_success_view(request, booking_id):
    """Страница подтверждения брони"""
    if not hasattr(request.user, 'guest_profile'):
        return redirect('core:owner_dashboard')
    
    booking = Booking.objects.get(id=booking_id, user=request.user)
    
    context = {
        'booking': booking,
        'guest_profile': request.user.guest_profile,
    }
    return render(request, 'booking_success.html', context)

from .models import Favorite  # Убедись, что Favorite импортирован в самом верху файла!


# ==========================================
# ИЗБРАННОЕ (добавить/убрать)
# ==========================================
@login_required
def toggle_favorite_view(request, slug):
    """Добавляет или удаляет ресторан из избранного (toggle)"""
    if not hasattr(request.user, 'guest_profile'):
        return redirect('core:owner_dashboard')
    
    restaurant = Restaurant.objects.get(slug=slug)
    
    # Ищем существующую запись в избранном
    favorite, created = Favorite.objects.get_or_create(
        user=request.user,
        restaurant=restaurant
    )
    
    if not created:
        # Если уже в избранном — удаляем
        favorite.delete()
    
    # Возвращаемся на страницу, откуда пришли
    # (используем HTTP_REFERER, чтобы не делать редирект жёстко)
    referer = request.META.get('HTTP_REFERER', '')
    if referer:
        return redirect(referer)
    
    # Если referer нет — идём на главную
    return redirect('core:home')


# ==========================================
# СТРАНИЦА ИЗБРАННОГО
# ==========================================
@login_required
def favorites_view(request):
    """Страница со списком избранных ресторанов"""
    if not hasattr(request.user, 'guest_profile'):
        return redirect('core:owner_dashboard')
    
    # Получаем все избранные рестораны пользователя
    favorites = Favorite.objects.filter(user=request.user).select_related('restaurant').order_by('-created_at')
    
    context = {
        'favorites': favorites,
        'guest_profile': request.user.guest_profile,
    }
    return render(request, 'favorites.html', context)

from django.db.models import Q


# ==========================================
# ИСТОРИЯ ЗАКАЗОВ
# ==========================================
@login_required
def order_history_view(request):
    """Список всех бронирований гостя"""
    if not hasattr(request.user, 'guest_profile'):
        return redirect('core:owner_dashboard')
    
    # Фильтр по статусу (если передан в GET-параметре)
    status_filter = request.GET.get('status', '')
    
    # Получаем все бронирования пользователя
    bookings = Booking.objects.filter(user=request.user).select_related('restaurant').order_by('-booking_datetime')
    
    if status_filter and status_filter != 'all':
        bookings = bookings.filter(status=status_filter)
    
    # Считаем количество по статусам для фильтров
    all_bookings = Booking.objects.filter(user=request.user)
    stats = {
        'all': all_bookings.count(),
        'upcoming': all_bookings.filter(status='confirmed', booking_datetime__gte=timezone.now()).count(),
        'completed': all_bookings.filter(status='completed').count(),
        'cancelled': all_bookings.filter(status__in=['cancelled_by_user', 'cancelled_by_restaurant']).count(),
    }
    
    context = {
        'bookings': bookings,
        'stats': stats,
        'current_filter': status_filter or 'all',
        'guest_profile': request.user.guest_profile,
    }
    return render(request, 'order_history.html', context)


# ==========================================
# ДЕТАЛИ БРОНИРОВАНИЯ
# ==========================================
@login_required
def booking_detail_view(request, booking_id):
    """Страница с деталями конкретной брони"""
    if not hasattr(request.user, 'guest_profile'):
        return redirect('core:owner_dashboard')
    
    booking = Booking.objects.get(id=booking_id, user=request.user)
    
    context = {
        'booking': booking,
        'guest_profile': request.user.guest_profile,
    }
    return render(request, 'booking_detail.html', context)


# ==========================================
# ОТМЕНА БРОНИРОВАНИЯ
# ==========================================
@login_required
def cancel_booking_view(request, booking_id):
    """Отмена бронирования"""
    if not hasattr(request.user, 'guest_profile'):
        return redirect('core:owner_dashboard')
    
    booking = Booking.objects.get(id=booking_id, user=request.user)
    
    # Можно отменить только подтверждённые или ожидающие брони
    if booking.status in ['pending', 'confirmed']:
        # Проверяем, что бронь ещё не состоялась
        if booking.booking_datetime > timezone.now():
            booking.status = 'cancelled_by_user'
            booking.save()
            
            # Обновляем статистику гостя
            guest_profile = request.user.guest_profile
            guest_profile.cancelled_bookings += 1
            guest_profile.save()
            guest_profile.calculate_reputation_and_cashback()
            
            messages.success(request, 'Бронирование успешно отменено')
        else:
            messages.error(request, 'Нельзя отменить прошедшую бронь')
    else:
        messages.error(request, 'Эту бронь нельзя отменить')
    
    return redirect('core:order_history')

from django.db.models import Avg, Count, Sum, Q, F
from django.db.models.functions import TruncDate, TruncWeek, TruncMonth


# ==========================================
# СПИСОК РЕСТОРАНОВ ВЛАДЕЛЬЦА
# ==========================================
@login_required
def owner_restaurants_view(request):
    """Список всех ресторанов владельца"""
    if not hasattr(request.user, 'owner_profile'):
        return redirect('core:home')
    
    owner_profile = request.user.owner_profile
    restaurants = owner_profile.restaurants.all().order_by('name')
    
    # Общая статистика по всем ресторанам
    all_bookings = Booking.objects.filter(restaurant__owner=owner_profile)
    total_revenue = all_bookings.filter(status='completed').aggregate(
        total=Sum('amount')
    )['total'] or 0
    total_bookings_count = all_bookings.count()
    total_reviews = Review.objects.filter(restaurant__owner=owner_profile).count()
    
    context = {
        'owner_profile': owner_profile,
        'restaurants': restaurants,
        'total_revenue': total_revenue,
        'total_bookings_count': total_bookings_count,
        'total_reviews': total_reviews,
    }
    return render(request, 'owner/restaurants.html', context)


# ==========================================
# ДОБАВЛЕНИЕ НОВОГО РЕСТОРАНА
# ==========================================
@login_required
def add_restaurant_view(request):
    """Форма добавления нового ресторана"""
    if not hasattr(request.user, 'owner_profile'):
        return redirect('core:home')
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        city = request.POST.get('city', '').strip()
        address = request.POST.get('address', '').strip()
        cuisine_type = request.POST.get('cuisine_type', '').strip()
        avg_check = request.POST.get('avg_check', 0)
        working_hours = request.POST.get('working_hours', '').strip()
        description = request.POST.get('description', '').strip()
        phone = request.POST.get('phone', '').strip()
        
        # Валидация
        if not all([name, city, address, cuisine_type, phone]):
            messages.error(request, 'Заполните все обязательные поля')
            return render(request, 'owner/add_restaurant.html')
        
        try:
            avg_check = int(avg_check)
        except (ValueError, TypeError):
            avg_check = 0
        
        # === БЕЗОПАСНАЯ ГЕНЕРАЦИЯ SLUG ===
        import re
        import uuid
        from django.utils.text import slugify
        
        base_slug = slugify(name)
        
        # Если название на кириллице, slugify вернет пустую строку. Исправляем это:
        if not base_slug or not re.match(r'^[a-zA-Z0-9_-]+$', base_slug):
            base_slug = f"rest-{uuid.uuid4().hex[:8]}"
        
        slug = base_slug
        counter = 1
        while Restaurant.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        # ==================================
        
        # Создаём ресторан
        restaurant = Restaurant.objects.create(
            owner=request.user.owner_profile,
            name=name,
            slug=slug,
            city=city,
            address=address,
            cuisine_type=cuisine_type,
            avg_check=avg_check,
            working_hours=working_hours or '10:00 - 00:00',
            description=description,
            phone=phone,
            is_active=True,
        )
        
        messages.success(request, f'Ресторан "{name}" успешно добавлен!')
        return redirect('core:restaurant_analytics', slug=restaurant.slug)
    
    return render(request, 'owner/add_restaurant.html')

from django.shortcuts import render, redirect, get_object_or_404 # <-- Убедись, что get_object_or_404 здесь есть

# ... (тут твои остальные view) ...

# ==========================================
# РЕДАКТИРОВАНИЕ РЕСТОРАНА
# ==========================================
@login_required
def edit_restaurant_view(request, slug):
    """Форма редактирования существующего ресторана"""
    if not hasattr(request.user, 'owner_profile'):
        return redirect('core:home')
    
    restaurant = get_object_or_404(Restaurant, slug=slug, owner=request.user.owner_profile)
    
    if request.method == 'POST':
        # Основные поля
        restaurant.name = request.POST.get('name', '').strip()
        restaurant.city = request.POST.get('city', '').strip()
        restaurant.address = request.POST.get('address', '').strip()
        restaurant.cuisine_type = request.POST.get('cuisine_type', '').strip()
        restaurant.subtitle = request.POST.get('subtitle', '').strip()
        restaurant.features = request.POST.get('features', '').strip()
        restaurant.kitchen_hours = request.POST.get('kitchen_hours', '').strip()
        
        try:
            restaurant.avg_check = int(request.POST.get('avg_check', 0))
        except (ValueError, TypeError):
            pass
            
        restaurant.working_hours = request.POST.get('working_hours', '').strip()
        restaurant.description = request.POST.get('description', '').strip()
        restaurant.phone = request.POST.get('phone', '').strip()
        restaurant.is_active = request.POST.get('is_active') == 'on'
        
        # Поля для метрик (те, что ты оставила)
        try:
            restaurant.current_occupancy = int(request.POST.get('current_occupancy', 0))
            restaurant.current_noise_level = int(request.POST.get('current_noise_level', 0))
            restaurant.current_service_time = int(request.POST.get('current_service_time', 0))
        except (ValueError, TypeError):
            pass
        
        # === ОБРАБОТКА ФОТО (УДАЛЕНИЕ И ЗАГРУЗКА) ===
        # 1. Получаем список фото, которые нужно удалить
        photos_to_delete = request.POST.getlist('delete_photos')
        
        # 2. Берем текущие фото, но убираем из списка те, что отмечены на удаление
        current_gallery = restaurant.gallery_images if restaurant.gallery_images else []
        gallery_urls = [url for url in current_gallery if url not in photos_to_delete]
        
        # 3. Загружаем новые фото (если есть)
        if request.FILES.getlist('gallery_photos'):
            import os
            from django.conf import settings
            import uuid
            
            gallery_dir = os.path.join(settings.MEDIA_ROOT, 'restaurant_gallery')
            os.makedirs(gallery_dir, exist_ok=True)
            
            for photo in request.FILES.getlist('gallery_photos'):
                file_extension = os.path.splitext(photo.name)[1].lower()
                new_filename = f"{uuid.uuid4().hex}{file_extension}"
                file_path = os.path.join(gallery_dir, new_filename)
                
                with open(file_path, 'wb+') as destination:
                    for chunk in photo.chunks():
                        destination.write(chunk)
                
                gallery_urls.append(f'{settings.MEDIA_URL}restaurant_gallery/{new_filename}')
        
        # 4. Сохраняем обновленный список
        restaurant.gallery_images = gallery_urls
        # ==============================================
        
        restaurant.save()
        
        messages.success(request, f'Ресторан "{restaurant.name}" успешно обновлен!')
        return redirect('core:restaurant_analytics', slug=restaurant.slug)
    
    context = {
        'restaurant': restaurant,
        'owner_profile': request.user.owner_profile,
    }
    return render(request, 'owner/edit_restaurant.html', context)

# ==========================================
# АНАЛИТИКА ПО КОНКРЕТНОМУ РЕСТОРАНУ
# ==========================================
@login_required
def restaurant_analytics_view(request, slug):
    """Страница аналитики ресторана с реальными данными"""
    if not hasattr(request.user, 'owner_profile'):
        return redirect('core:home')
    
    restaurant = get_object_or_404(Restaurant, slug=slug, owner=request.user.owner_profile)
    
    period = request.GET.get('period', 'month')
    tab = request.GET.get('tab', 'attendance')
    
    now = timezone.now()
    if period == 'day':
        start_date = now - timedelta(days=1)
    elif period == 'week':
        start_date = now - timedelta(weeks=1)
    elif period == 'month':
        start_date = now - timedelta(days=30)
    elif period == 'quarter':
        start_date = now - timedelta(days=90)
    elif period == 'year':
        start_date = now - timedelta(days=365)
    else:
        start_date = now - timedelta(days=30)
    
    bookings = Booking.objects.filter(restaurant=restaurant, booking_datetime__gte=start_date)
    completed_bookings = bookings.filter(status='completed')
    cancelled_bookings = bookings.filter(status__in=['cancelled_by_user', 'cancelled_by_restaurant'])
    
    avg_check_data = completed_bookings.aggregate(avg=Avg('amount'))
    avg_check = round(avg_check_data['avg'] or 0)
    
    unique_guests = bookings.exclude(user=None).values('user').distinct().count()
    tables_served = completed_bookings.count()
    
    guest_visits = bookings.exclude(user=None).values('user').annotate(visits=Count('id'))
    repeat_guests = guest_visits.filter(visits__gt=1).count()
    repeat_visits_percent = round((repeat_guests / unique_guests * 100) if unique_guests > 0 else 0)
    
    total_revenue = completed_bookings.aggregate(total=Sum('amount'))['total'] or 0
    visit_frequency = round(bookings.exclude(user=None).count() / unique_guests, 1) if unique_guests > 0 else 0
    
    sources_data = bookings.values('source').annotate(count=Count('id')).order_by('-count')
    total_for_sources = bookings.count() or 1
    sources = []
    for item in sources_data:
        sources.append({
            'source': item['source'],
            'label': dict(Booking.SOURCE_CHOICES).get(item['source'], item['source']),
            'count': item['count'],
            'percent': round(item['count'] / total_for_sources * 100),
        })
    
    total_bookings_count = bookings.count()
    cancelled_count = cancelled_bookings.count()
    cancellation_rate = round((cancelled_count / total_bookings_count * 100) if total_bookings_count > 0 else 0, 1)
    
    # === БЕЗОПАСНЫЙ РАСЧЕТ ОТЗЫВОВ (без IndexError) ===
    reviews_qs = Review.objects.filter(restaurant=restaurant, created_at__gte=start_date)
    reviews_count = reviews_qs.count()
    avg_rating_data = reviews_qs.aggregate(avg=Avg('rating'))
    avg_rating = round(avg_rating_data['avg'] or 0, 1)
    
    rating_dist = []
    for i in range(5, 0, -1):
        count = reviews_qs.filter(rating=i).count()
        rating_dist.append({'stars': i, 'count': count})
    # ================================================
    
        # Посещаемость по дням (с защитой от пустых дат)
    attendance = bookings.annotate(date=TruncDate('booking_datetime')).values('date').annotate(count=Count('id')).order_by('date')
    attendance_labels = [item['date'].strftime('%d.%m') for item in attendance if item['date'] is not None]
    attendance_values = [item['count'] for item in attendance if item['date'] is not None]
    
    staff = restaurant.staff.all().order_by('-csat_score')
    
        # === БРОНИРОВАНИЯ (для вкладки "Бронирования") ===
    all_bookings = Booking.objects.filter(restaurant=restaurant).order_by('-booking_datetime')
    upcoming_bookings = all_bookings.filter(status='confirmed', booking_datetime__gte=timezone.now())
    completed_bookings_list = all_bookings.filter(status='completed')
    cancelled_bookings_list = all_bookings.filter(status__in=['cancelled_by_user', 'cancelled_by_restaurant'])
    
    # === ОТЗЫВЫ (для вкладки "Рейтинги") ===
    all_restaurant_reviews = Review.objects.filter(restaurant=restaurant, is_moderated=True).order_by('-created_at')[:10]

    context = {
        'restaurant': restaurant,
        'period': period,
        'tab': tab,
        'avg_check': avg_check,
        'unique_guests': unique_guests,
        'tables_served': tables_served,
        'repeat_visits_percent': repeat_visits_percent,
        'total_revenue': total_revenue,
        'visit_frequency': visit_frequency,
        'sources': sources,
        'cancellation_rate': cancellation_rate,
        'cancelled_count': cancelled_count,
        'total_bookings': total_bookings_count,
        'reviews_count': reviews_count,
        'avg_rating': avg_rating,
        'rating_dist': rating_dist,
        'attendance_labels': attendance_labels,
        'attendance_values': attendance_values,
        'staff': staff,'all_bookings': all_bookings[:20],  # Последние 20 броней
        'upcoming_bookings': upcoming_bookings,
        'completed_bookings_list': completed_bookings_list[:10],
        'cancelled_bookings_list': cancelled_bookings_list[:10],
        'all_restaurant_reviews': all_restaurant_reviews,
    }
    return render(request, 'owner/analytics.html', context)

@login_required
def add_review_view(request, slug):
    """Добавление отзыва пользователем"""
    if not hasattr(request.user, 'guest_profile'):
        return redirect('core:login')
    
    restaurant = get_object_or_404(Restaurant, slug=slug)
    
    if request.method == 'POST':
        # Создаем новый отзыв в базе данных
        Review.objects.create(
            user=request.user,
            restaurant=restaurant,
            text=request.POST.get('text', '').strip(),
            rating=int(request.POST.get('rating', 5)),
            service_rating=int(request.POST.get('service_rating', 5)),
            price_quality_rating=int(request.POST.get('price_quality_rating', 5)),
            atmosphere_rating=int(request.POST.get('atmosphere_rating', 5)),
            is_moderated=True  # В демо-режиме отзыв публикуется сразу
        )
        
        messages.success(request, 'Спасибо за ваш отзыв! Он успешно опубликован.')
        return redirect('core:restaurant_detail', slug=slug)
    
    # Если запрос не POST, просто возвращаем на страницу ресторана
    return redirect('core:restaurant_detail', slug=slug)