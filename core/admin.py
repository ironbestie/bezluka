from django.contrib import admin
from .models import (
    GuestProfile, OwnerProfile, Restaurant, StaffMember, Booking,
    Favorite, Review, Menu, MenuCategory, MenuItem,
    Event, EventRegistration, LoyaltyTransaction,
    PromoCode, UserPromoCode, Address, Notification, AccessLog
)


# ==========================================
# ПРОФИЛИ
# ==========================================
@admin.register(GuestProfile)
class GuestProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'loyalty_level', 'points_balance', 'cashback_percent', 'reputation_score', 'total_bookings', 'phone')
    search_fields = ('user__first_name', 'user__username', 'phone')
    list_filter = ('loyalty_level',)
    readonly_fields = ('reputation_score', 'cashback_percent', 'total_bookings', 'completed_bookings', 'cancelled_bookings', 'total_spent', 'monthly_spent')
    
    actions = ['recalculate_reputation']
    
    def recalculate_reputation(self, request, queryset):
        for profile in queryset:
            profile.calculate_reputation_and_cashback()
        self.message_user(request, f"Пересчитано {queryset.count()} профилей")
    recalculate_reputation.short_description = "Пересчитать репутацию и кэшбэк"


@admin.register(OwnerProfile)
class OwnerProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'company_name', 'inn', 'position')
    search_fields = ('user__first_name', 'company_name', 'inn')


# ==========================================
# РЕСТОРАНЫ И ПЕРСОНАЛ
# ==========================================
@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    list_display = ('name', 'city', 'cuisine_type', 'avg_check', 'overall_rating', 'total_reviews', 'is_active')
    list_filter = ('city', 'cuisine_type', 'is_active')
    search_fields = ('name', 'address')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(StaffMember)
class StaffMemberAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'position', 'restaurant', 'csat_score', 'reviews_count', 'complaints_count', 'tips_total')
    list_filter = ('position', 'restaurant')
    search_fields = ('full_name',)


# ==========================================
# БРОНИРОВАНИЯ
# ==========================================
@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('booking_datetime', 'guest_name', 'restaurant', 'source', 'status', 'party_size', 'amount')
    list_filter = ('status', 'source', 'restaurant', 'booking_datetime')
    search_fields = ('guest_name', 'guest_phone', 'external_booking_id')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'booking_datetime'


# ==========================================
# ИЗБРАННОЕ И ОТЗЫВЫ
# ==========================================
@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ('user', 'restaurant', 'created_at')
    list_filter = ('restaurant',)
    search_fields = ('user__first_name', 'restaurant__name')


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('restaurant', 'user', 'staff_member', 'review_type', 'rating', 'is_moderated', 'created_at')
    list_filter = ('rating', 'review_type', 'is_moderated', 'restaurant', 'created_at')
    search_fields = ('text', 'user__first_name')


# ==========================================
# МЕНЮ
# ==========================================
@admin.register(Menu)
class MenuAdmin(admin.ModelAdmin):
    list_display = ('name', 'restaurant', 'is_active')
    list_filter = ('restaurant', 'is_active')


@admin.register(MenuCategory)
class MenuCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'menu', 'sort_order')


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'is_popular', 'is_new', 'is_chef_recommended', 'is_active')
    list_filter = ('category__menu__restaurant', 'is_popular', 'is_new', 'is_chef_recommended', 'is_active')
    search_fields = ('name',)


# ==========================================
# СОБЫТИЯ
# ==========================================
@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'restaurant', 'event_datetime', 'max_participants', 'is_active')
    list_filter = ('restaurant', 'is_active')
    search_fields = ('title',)


@admin.register(EventRegistration)
class EventRegistrationAdmin(admin.ModelAdmin):
    list_display = ('user', 'event', 'status', 'registered_at')
    list_filter = ('status', 'event')


# ==========================================
# ЛОЯЛЬНОСТЬ И ПРОМОКОДЫ
# ==========================================
@admin.register(LoyaltyTransaction)
class LoyaltyTransactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'points_change', 'reason', 'related_booking', 'timestamp')
    list_filter = ('reason', 'timestamp')
    search_fields = ('user__first_name', 'user__username')
    date_hierarchy = 'timestamp'


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount_percent', 'discount_amount', 'valid_from', 'valid_until', 'current_uses', 'max_uses', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('code',)


@admin.register(UserPromoCode)
class UserPromoCodeAdmin(admin.ModelAdmin):
    list_display = ('user', 'promo_code', 'activated_at', 'is_used')
    list_filter = ('is_used',)


# ==========================================
# АДРЕСА И УВЕДОМЛЕНИЯ
# ==========================================
@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'full_address', 'is_default')
    search_fields = ('user__first_name', 'full_address')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'type', 'is_read', 'created_at')
    list_filter = ('type', 'is_read', 'created_at')
    search_fields = ('title', 'message')


# ==========================================
# АУДИТ (только для чтения!)
# ==========================================
@admin.register(AccessLog)
class AccessLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'action', 'ip_address', 'target_object')
    list_filter = ('action', 'timestamp')
    readonly_fields = ('timestamp', 'user', 'ip_address', 'action', 'target_object', 'details')
    date_hierarchy = 'timestamp'
    
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False