from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone


# ==========================================
# 1. ПРОФИЛИ ПОЛЬЗОВАТЕЛЕЙ
# ==========================================
class GuestProfile(models.Model):
    """
    Профиль гостя.
    Репутация и кэшбэк (2-10%) считаются автоматически на основе:
    - количества броней
    - процента отмен
    - общей суммы трат за месяц
    """
    LOYALTY_LEVEL_CHOICES = (
        ('Select', 'Select'),
        ('Silver', 'Silver'),
        ('Gold', 'Gold'),
        ('Platinum', 'Platinum'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='guest_profile', verbose_name="Пользователь")
    
    # Основные данные гостя
    phone = models.CharField(max_length=20, blank=True, verbose_name="Телефон")
    date_of_birth = models.DateField(blank=True, null=True, verbose_name="Дата рождения")
    gender = models.CharField(max_length=15, blank=True, verbose_name="Пол")
    marketing_consent = models.BooleanField(default=False, verbose_name="Согласие на рассылки (152-ФЗ)")
    
    # Статистика поведения (для расчёта репутации)
    total_bookings = models.IntegerField(default=0, verbose_name="Всего броней")
    completed_bookings = models.IntegerField(default=0, verbose_name="Состоявшихся броней")
    cancelled_bookings = models.IntegerField(default=0, verbose_name="Отменённых броней")
    total_spent = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Общая сумма трат (₽)")
    monthly_spent = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Траты за текущий месяц (₽)")
    
    # Репутация и лояльность
    reputation_score = models.IntegerField(default=0, verbose_name="Репутация (0-100)")
    cashback_percent = models.IntegerField(default=2, verbose_name="Кэшбэк % (2-10%)")
    loyalty_level = models.CharField(max_length=10, choices=LOYALTY_LEVEL_CHOICES, default='Select', verbose_name="Уровень лояльности")
    points_balance = models.IntegerField(default=500, verbose_name="Баланс баллов (500 приветственных)")
    
    # Реферальная программа
    referral_code = models.CharField(max_length=20, unique=True, blank=True, null=True, verbose_name="Реферальный код")
    referred_by = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='referrals', verbose_name="Пришёл по рефералу от")

    class Meta:
        verbose_name = "Профиль гостя"
        verbose_name_plural = "Профили гостей"

    def __str__(self):
        return f"{self.user.first_name} ({self.points_balance} баллов, {self.cashback_percent}%)"

    def calculate_reputation_and_cashback(self):
        """
        Пересчитывает репутацию и кэшбэк на основе поведения гостя.
        Кэшбэк: от 2% (новичок) до 10% (Platinum).
        """
        if self.total_bookings == 0:
            self.reputation_score = 0
            self.cashback_percent = 2
            self.loyalty_level = 'Select'
            self.save()
            return

        # Коэффициент надёжности (0.0 - 1.0): чем меньше отмен, тем лучше
        cancellation_rate = self.cancelled_bookings / self.total_bookings
        reliability_score = max(0, 1 - cancellation_rate * 2)

        # Коэффициент активности (0.0 - 1.0): 20+ броней = максимум
        activity_score = min(1.0, self.total_bookings / 20)

        # Коэффициент трат (0.0 - 1.0): средний чек 5000+ ₽ = максимум
        avg_check = self.total_spent / max(1, self.completed_bookings)
        spending_score = min(1.0, avg_check / 5000)

        # Итоговая репутация (0-100)
        self.reputation_score = int(
            reliability_score * 50 + activity_score * 30 + spending_score * 20
        )

        # Маппинг репутации → кэшбэк и уровень
        if self.reputation_score >= 80:
            self.cashback_percent = 10
            self.loyalty_level = 'Platinum'
        elif self.reputation_score >= 60:
            self.cashback_percent = 7
            self.loyalty_level = 'Gold'
        elif self.reputation_score >= 40:
            self.cashback_percent = 5
            self.loyalty_level = 'Silver'
        else:
            self.cashback_percent = 2
            self.loyalty_level = 'Select'

        self.save()


class OwnerProfile(models.Model):
    """Профиль владельца ресторана — компания, ИНН, доступ"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='owner_profile', verbose_name="Пользователь")
    company_name = models.CharField(max_length=200, blank=True, verbose_name="Название юр. лица / ИП")
    inn = models.CharField(max_length=12, blank=True, verbose_name="ИНН")
    position = models.CharField(max_length=50, blank=True, verbose_name="Должность")

    class Meta:
        verbose_name = "Профиль владельца"
        verbose_name_plural = "Профили владельцев"

    def __str__(self):
        return f"{self.user.first_name} ({self.company_name or 'Без названия'})"


# ==========================================
# 2. РЕСТОРАНЫ
# ==========================================
class Restaurant(models.Model):
    """Карточка ресторана"""
    owner = models.ForeignKey(OwnerProfile, on_delete=models.CASCADE, related_name='restaurants', verbose_name="Владелец")
    name = models.CharField(max_length=200, verbose_name="Название ресторана")
    slug = models.SlugField(max_length=100, unique=True, verbose_name="URL-слаб (ЧПУ)")
    city = models.CharField(max_length=100, verbose_name="Город")
    address = models.CharField(max_length=255, verbose_name="Адрес")
    coordinates = models.CharField(max_length=100, blank=True, verbose_name="Координаты (широта, долгота)")
    cuisine_type = models.CharField(max_length=100, verbose_name="Тип кухни")
    avg_check = models.IntegerField(verbose_name="Средний чек (₽)", validators=[MinValueValidator(1)])
    working_hours = models.CharField(max_length=100, verbose_name="График работы")
    description = models.TextField(blank=True, verbose_name="Описание")
    phone = models.CharField(max_length=20, verbose_name="Телефон ресторана")
    image_url = models.CharField(max_length=500, blank=True, verbose_name="Главное фото")
    
    # Ключевое поле для интеграций с iiko, TheFork, LeClick и др.
    # Хранит JSON: {"iiko": "uuid-123", "thefork": "tf-456", "leclick": "lc-789"}
    external_ids = models.JSONField(default=dict, blank=True, verbose_name="Внешние ID для интеграций")
    
    # Кэшированные метрики (обновляются автоматически)
    overall_rating = models.DecimalField(max_digits=3, decimal_places=1, default=0.0, verbose_name="Общий рейтинг")
    total_reviews = models.IntegerField(default=0, verbose_name="Количество отзывов")
    return_rate = models.IntegerField(default=0, verbose_name="Возвращаемость (%)")
    recommend_rate = models.IntegerField(default=0, verbose_name="Рекомендуют (%)")
    
    is_active = models.BooleanField(default=True, verbose_name="Активен (виден в приложении)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    # === НОВЫЕ ПОЛЯ ИЗ PDF ===
    subtitle = models.CharField(max_length=200, blank=True, verbose_name="Подзаголовок/слоган")
    features = models.TextField(blank=True, verbose_name="Фишки заведения")
    return_rate = models.IntegerField(default=0, verbose_name="Возвращаемость (%)")
    recommend_count = models.IntegerField(default=0, verbose_name="Людей рекомендует")
    match_percent = models.IntegerField(default=0, verbose_name="Вам подходит (%)")
    
    # Real-time метрики (можно обновлять вручную или автоматически)
    current_occupancy = models.IntegerField(default=0, verbose_name="Текущая загруженность (%)")
    current_noise_level = models.IntegerField(default=0, verbose_name="Текущий уровень шума (%)")
    current_service_time = models.IntegerField(default=0, verbose_name="Текущее время обслуживания (мин)")
    
    # Детали работы
    kitchen_hours = models.CharField(max_length=100, blank=True, verbose_name="Часы работы кухни")
    
    # Рейтинг персонала (агрегированные данные)
    staff_service_rating = models.DecimalField(max_digits=3, decimal_places=1, default=0, verbose_name="Качество обслуживания")
    staff_price_quality_rating = models.DecimalField(max_digits=3, decimal_places=1, default=0, verbose_name="Соответствие цена/качество")
    staff_atmosphere_rating = models.DecimalField(max_digits=3, decimal_places=1, default=0, verbose_name="Атмосфера")
    
    gallery_images = models.JSONField(default=list, blank=True, verbose_name="Ссылки на фото галереи")

    class Meta:
        verbose_name = "Ресторан"
        verbose_name_plural = "Рестораны"
        indexes = [
            models.Index(fields=['city', 'cuisine_type']),
        ]

    def __str__(self):
        return self.name


# ==========================================
# 3. ПЕРСОНАЛ (НЕ пользователи! Просто сотрудники)
# ==========================================
class StaffMember(models.Model):
    """
    Сотрудник ресторана.
    Это НЕ роль пользователя, а тип персонала, которому гости оставляют оценки.
    """
    POSITION_CHOICES = (
        ('waiter', 'Официант'),
        ('senior_waiter', 'Старший официант'),
        ('bartender', 'Бармен'),
        ('chef', 'Шеф-повар'),
        ('cook', 'Повар'),
        ('admin', 'Администратор'),
    )

    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='staff', verbose_name="Ресторан")
    full_name = models.CharField(max_length=150, verbose_name="ФИО")
    position = models.CharField(max_length=20, choices=POSITION_CHOICES, verbose_name="Должность")
    experience_years = models.IntegerField(default=0, verbose_name="Опыт работы (лет)")
    photo_url = models.CharField(max_length=500, blank=True, verbose_name="Фото")
    
    # Метрики (считаются автоматически из отзывов)
    csat_score = models.IntegerField(default=0, verbose_name="Рейтинг CSAT (%)")
    complaints_count = models.IntegerField(default=0, verbose_name="Количество жалоб")
    badges_count = models.IntegerField(default=0, verbose_name="Получено бейджей")
    tips_total = models.IntegerField(default=0, verbose_name="Сумма чаевых (₽)")
    reviews_count = models.IntegerField(default=0, verbose_name="Количество отзывов")

    class Meta:
        verbose_name = "Сотрудник"
        verbose_name_plural = "Сотрудники"

    def __str__(self):
        return f"{self.full_name} ({self.get_position_display()})"


# ==========================================
# 4. БРОНИРОВАНИЯ (центр интеграций)
# ==========================================
class Booking(models.Model):
    """
    Бронирование стола.
    Брони приходят через API агрегаторов (TheFork, LeClick, Smartreserve и др.)
    """
    SOURCE_CHOICES = (
        ('bezluka_web', 'Сайт БезЛука'),
        ('thefork', 'TheFork'),
        ('leclick', 'LeClick'),
        ('tomesto', 'ТоМесто'),
        ('allcafe', 'Allcafe'),
        ('restoclub', 'Restoclub'),
        ('restorating', 'Restorating'),
        ('restoran_ru', 'Restoran.ru'),
        ('afisha', 'Afisha'),
        ('opentable', 'OpenTable'),
        ('resy', 'Resy'),
        ('quandoo', 'Quandoo'),
        ('smartreserve', 'Smartreserve'),
        ('remarked', 'Remarked'),
        ('hostme', 'Hostme'),
        ('phone', 'Телефон'),
    )
    STATUS_CHOICES = (
        ('pending', 'Ожидает подтверждения'),
        ('confirmed', 'Подтверждено'),
        ('rejected', 'Отклонено'),
        ('cancelled_by_user', 'Отменено гостем'),
        ('cancelled_by_restaurant', 'Отменено рестораном'),
        ('completed', 'Состоялось'),
        ('no_show', 'Не пришел'),
    )

    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='bookings', verbose_name="Ресторан")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='bookings', verbose_name="Гость")
    
    guest_name = models.CharField(max_length=100, verbose_name="Имя гостя")
    guest_phone = models.CharField(max_length=20, verbose_name="Телефон гостя")
    party_size = models.IntegerField(verbose_name="Количество персон", validators=[MinValueValidator(1)])
    booking_datetime = models.DateTimeField(verbose_name="Дата и время визита")
    comment = models.TextField(blank=True, verbose_name="Пожелания")
    
    # ВАЖНО: сумма чека нужна для расчёта лояльности!
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Сумма чека (₽)")
    
    source = models.CharField(max_length=30, choices=SOURCE_CHOICES, verbose_name="Источник брони")
    external_booking_id = models.CharField(max_length=100, blank=True, null=True, unique=True, verbose_name="Внешний ID брони")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending', verbose_name="Статус")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")

    class Meta:
        verbose_name = "Бронирование"
        verbose_name_plural = "Бронирования"
        ordering = ['-booking_datetime']
        indexes = [
            models.Index(fields=['restaurant', 'booking_datetime']),
            models.Index(fields=['status', 'booking_datetime']),
        ]

    def __str__(self):
        return f"{self.guest_name} → {self.restaurant.name} ({self.booking_datetime.strftime('%d.%m %H:%M')})"


# ==========================================
# 5. ИЗБРАННОЕ
# ==========================================
class Favorite(models.Model):
    """Избранные рестораны гостя"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorites', verbose_name="Гость")
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='favorited_by', verbose_name="Ресторан")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Добавлено")

    class Meta:
        verbose_name = "Избранное"
        verbose_name_plural = "Избранное"
        unique_together = [['user', 'restaurant']]

    def __str__(self):
        return f"{self.user.first_name} ♡ {self.restaurant.name}"


# ==========================================
# 6. ОТЗЫВЫ (на персонал + ресторан)
# ==========================================
class Review(models.Model):
    """
    Отзыв с привязкой к ресторану И/ИЛИ конкретному сотруднику.
    review_type определяет, что именно оценили.
    """
    REVIEW_TYPE_CHOICES = (
        ('restaurant', 'Только ресторан'),
        ('staff', 'Только сотрудник'),
        ('both', 'И ресторан, и сотрудник'),
    )
    # === НОВЫЕ ПОЛЯ: оценки персонала от пользователя ===
    service_rating = models.IntegerField(default=5, verbose_name="Качество обслуживания")
    price_quality_rating = models.IntegerField(default=5, verbose_name="Соответствие цена/качество")
    atmosphere_rating = models.IntegerField(default=5, verbose_name="Атмосфера")

    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='reviews', verbose_name="Ресторан")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviews', verbose_name="Автор")
    staff_member = models.ForeignKey(StaffMember, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviews', verbose_name="Оцененный сотрудник")
    
    review_type = models.CharField(max_length=15, choices=REVIEW_TYPE_CHOICES, default='restaurant', verbose_name="Тип отзыва")
    rating = models.IntegerField(verbose_name="Оценка (1-5)", validators=[MinValueValidator(1), MaxValueValidator(5)])
    text = models.TextField(blank=True, verbose_name="Текст отзыва")
    is_moderated = models.BooleanField(default=False, verbose_name="Прошел модерацию")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата")

    class Meta:
        verbose_name = "Отзыв"
        verbose_name_plural = "Отзывы"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.restaurant.name}: {self.rating}★"


# ==========================================
# 7. МЕНЮ РЕСТОРАНА
# ==========================================
class Menu(models.Model):
    """Меню ресторана"""
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='menus', verbose_name="Ресторан")
    name = models.CharField(max_length=100, verbose_name="Название меню")
    is_active = models.BooleanField(default=True, verbose_name="Активно")

    class Meta:
        verbose_name = "Меню"
        verbose_name_plural = "Меню"

    def __str__(self):
        return f"{self.restaurant.name} — {self.name}"


class MenuCategory(models.Model):
    """Категория блюд (Салаты, Паста, Десерты)"""
    menu = models.ForeignKey(Menu, on_delete=models.CASCADE, related_name='categories', verbose_name="Меню")
    name = models.CharField(max_length=100, verbose_name="Категория")
    sort_order = models.IntegerField(default=0, verbose_name="Порядок отображения")

    class Meta:
        verbose_name = "Категория меню"
        verbose_name_plural = "Категории меню"
        ordering = ['sort_order']

    def __str__(self):
        return self.name


class MenuItem(models.Model):
    """Конкретное блюдо"""
    category = models.ForeignKey(MenuCategory, on_delete=models.CASCADE, related_name='items', verbose_name="Категория")
    name = models.CharField(max_length=200, verbose_name="Название блюда")
    description = models.TextField(blank=True, verbose_name="Описание")
    price = models.IntegerField(verbose_name="Цена (₽)", validators=[MinValueValidator(0)])
    image_url = models.CharField(max_length=500, blank=True, verbose_name="URL фото")
    is_popular = models.BooleanField(default=False, verbose_name="Хит")
    is_new = models.BooleanField(default=False, verbose_name="Новинка")
    is_chef_recommended = models.BooleanField(default=False, verbose_name="Шеф рекомендует")
    is_active = models.BooleanField(default=True, verbose_name="В наличии")

    class Meta:
        verbose_name = "Блюдо"
        verbose_name_plural = "Блюда"

    def __str__(self):
        return f"{self.name} ({self.price} ₽)"


# ==========================================
# 8. СОБЫТИЯ
# ==========================================
class Event(models.Model):
    """Событие в ресторане (дегустация, вечер в стиле Gatsby и т.д.)"""
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='events', verbose_name="Ресторан")
    title = models.CharField(max_length=200, verbose_name="Название события")
    description = models.TextField(blank=True, verbose_name="Описание")
    event_datetime = models.DateTimeField(verbose_name="Дата и время", db_index=True)
    image_url = models.CharField(max_length=500, blank=True, verbose_name="Постер")
    max_participants = models.IntegerField(null=True, blank=True, verbose_name="Макс. участников", validators=[MinValueValidator(1)])
    is_active = models.BooleanField(default=True, verbose_name="Активно")

    class Meta:
        verbose_name = "Событие"
        verbose_name_plural = "События"
        ordering = ['-event_datetime']

    def __str__(self):
        return f"{self.title} ({self.event_datetime.strftime('%d.%m.%Y')})"


class EventRegistration(models.Model):
    """Регистрация гостя на событие"""
    STATUS_CHOICES = (
        ('registered', 'Зарегистрирован'),
        ('attended', 'Присутствовал'),
        ('cancelled', 'Отменено'),
    )

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='registrations', verbose_name="Событие")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='event_registrations', verbose_name="Гость")
    registered_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата регистрации")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='registered', verbose_name="Статус")

    class Meta:
        verbose_name = "Регистрация на событие"
        verbose_name_plural = "Регистрации на события"
        unique_together = [['event', 'user']]

    def __str__(self):
        return f"{self.user.first_name} → {self.event.title}"


# ==========================================
# 9. ЛОЯЛЬНОСТЬ: ТРАНЗАКЦИИ
# ==========================================
class LoyaltyTransaction(models.Model):
    """История движений баллов (для аудита и отображения в профиле)"""
    REASON_CHOICES = (
        ('registration', 'Приветственные баллы'),
        ('booking_cashback', 'Кэшбэк за бронь'),
        ('review', 'Бонус за отзыв'),
        ('referral', 'Реферальный бонус'),
        ('cancellation', 'Возврат при отмене'),
        ('redemption', 'Списание баллов'),
        ('manual', 'Ручная корректировка'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='loyalty_transactions', verbose_name="Пользователь")
    points_change = models.IntegerField(verbose_name="Изменение баллов (+/-)")
    reason = models.CharField(max_length=30, choices=REASON_CHOICES, verbose_name="Причина")
    related_booking = models.ForeignKey(Booking, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Связанная бронь")
    description = models.CharField(max_length=255, blank=True, verbose_name="Описание")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Время операции")

    class Meta:
        verbose_name = "Транзакция лояльности"
        verbose_name_plural = "Транзакции лояльности"
        ordering = ['-timestamp']

    def __str__(self):
        sign = "+" if self.points_change > 0 else ""
        return f"{self.user.first_name}: {sign}{self.points_change} баллов ({self.get_reason_display()})"


# ==========================================
# 10. ПРОМОКОДА
# ==========================================
class PromoCode(models.Model):
    """Промокод"""
    code = models.CharField(max_length=50, unique=True, verbose_name="Код")
    discount_percent = models.IntegerField(null=True, blank=True, verbose_name="Скидка (%)", validators=[MinValueValidator(0), MaxValueValidator(100)])
    discount_amount = models.IntegerField(null=True, blank=True, verbose_name="Скидка (₽)", validators=[MinValueValidator(0)])
    valid_from = models.DateTimeField(verbose_name="Начало действия")
    valid_until = models.DateTimeField(verbose_name="Окончание")
    max_uses = models.IntegerField(null=True, blank=True, verbose_name="Макс. использований", validators=[MinValueValidator(1)])
    current_uses = models.IntegerField(default=0, verbose_name="Текущее кол-во")
    is_active = models.BooleanField(default=True, verbose_name="Активен")

    class Meta:
        verbose_name = "Промокод"
        verbose_name_plural = "Промокоды"

    def __str__(self):
        return self.code


class UserPromoCode(models.Model):
    """Промокод, активированный пользователем"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='promo_codes', verbose_name="Пользователь")
    promo_code = models.ForeignKey(PromoCode, on_delete=models.CASCADE, verbose_name="Промокод")
    activated_at = models.DateTimeField(auto_now_add=True, verbose_name="Активирован")
    is_used = models.BooleanField(default=False, verbose_name="Использован")

    class Meta:
        verbose_name = "Промокод пользователя"
        verbose_name_plural = "Промокоды пользователей"
        unique_together = [['user', 'promo_code']]


# ==========================================
# 11. АДРЕСА ГОСТЯ
# ==========================================
class Address(models.Model):
    """Сохранённые адреса гостя"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses', verbose_name="Пользователь")
    title = models.CharField(max_length=50, verbose_name="Название (Дом, Работа)")
    full_address = models.CharField(max_length=255, verbose_name="Полный адрес")
    coordinates = models.CharField(max_length=100, blank=True, verbose_name="Координаты")
    is_default = models.BooleanField(default=False, verbose_name="По умолчанию")

    class Meta:
        verbose_name = "Адрес"
        verbose_name_plural = "Адреса"

    def __str__(self):
        return f"{self.title}: {self.full_address}"


# ==========================================
# 12. УВЕДОМЛЕНИЯ
# ==========================================
class Notification(models.Model):
    """Уведомления для пользователей"""
    TYPE_CHOICES = (
        ('booking', 'Бронирование'),
        ('promo', 'Промоакция'),
        ('loyalty', 'Лояльность'),
        ('system', 'Системное'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications', verbose_name="Пользователь")
    title = models.CharField(max_length=200, verbose_name="Заголовок")
    message = models.TextField(verbose_name="Сообщение")
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name="Тип")
    is_read = models.BooleanField(default=False, verbose_name="Прочитано")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата")

    class Meta:
        verbose_name = "Уведомление"
        verbose_name_plural = "Уведомления"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} → {self.user.first_name}"


# ==========================================
# 13. АУДИТ И БЕЗОПАСНОСТЬ (152-ФЗ)
# ==========================================
class AccessLog(models.Model):
    """Логи доступа к персональным данным (требование Роскомнадзора)"""
    ACTION_CHOICES = (
        ('login', 'Вход в систему'),
        ('logout', 'Выход из системы'),
        ('view_pd', 'Просмотр персональных данных'),
        ('export', 'Экспорт данных'),
    )

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='access_logs', verbose_name="Кто совершил")
    ip_address = models.GenericIPAddressField(verbose_name="IP-адрес")
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, verbose_name="Действие")
    target_object = models.CharField(max_length=255, blank=True, verbose_name="Объект доступа")
    details = models.TextField(blank=True, verbose_name="Детали")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Время")

    class Meta:
        verbose_name = "Лог доступа"
        verbose_name_plural = "Логи доступа"
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.timestamp.strftime('%d.%m %H:%M')}] {self.user} → {self.get_action_display()}"

# ==========================================
# 14. КОДЫ ПОДТВЕРЖДЕНИЯ (для входа по SMS)
# ==========================================
class VerificationCode(models.Model):
    """Храним коды подтверждения в БД для безопасности и аудита"""
    phone = models.CharField(max_length=20, verbose_name="Телефон")
    code = models.CharField(max_length=10, verbose_name="Код")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создан")
    expires_at = models.DateTimeField(verbose_name="Истекает")
    is_used = models.BooleanField(default=False, verbose_name="Использован")
    attempts = models.IntegerField(default=0, verbose_name="Попыток ввода")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP-адрес")
    
    class Meta:
        verbose_name = "Код подтверждения"
        verbose_name_plural = "Коды подтверждения"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.phone}: {self.code} (истёк: {self.expires_at.strftime('%H:%M')})"
    
    @property
    def is_expired(self):
        from django.utils import timezone
        return timezone.now() > self.expires_at
    
    @property
    def is_valid(self):
        return not self.is_expired and not self.is_used and self.attempts < 5
    
