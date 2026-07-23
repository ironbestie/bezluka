"""
Скрипт для наполнения базы данных тестовыми ресторанами, персоналом и меню.
Запуск: python manage.py seed_data
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import (
    Restaurant, StaffMember, Menu, MenuCategory, MenuItem,
    Review, OwnerProfile, GuestProfile
)
from decimal import Decimal


class Command(BaseCommand):
    help = 'Наполняет базу данных тестовыми ресторанами и данными'

    def handle(self, *args, **kwargs):
        self.stdout.write('🌱 Начинаем наполнение базы данных...')
        
        # ==========================================
        # 1. Создаём владельца (если ещё нет)
        # ==========================================
        owner_user, created = User.objects.get_or_create(
            username='+79001112233',
            defaults={
                'first_name': 'Иван',
                'last_name': 'Владелец',
            }
        )
        if created:
            OwnerProfile.objects.create(
                user=owner_user,
                company_name='ООО "Ресторанная группа БезЛука"',
                inn='7701234567',
                position='Владелец',
            )
            self.stdout.write(self.style.SUCCESS('✅ Создан владелец: Иван'))
        
        owner_profile = owner_user.owner_profile
        
        # ==========================================
        # 2. Создаём рестораны из макета
        # ==========================================
        restaurants_data = [
            {
                'name': 'White Rabbit',
                'slug': 'white-rabbit',
                'city': 'Москва',
                'address': 'Москва, Малая Дмитровка, 18Ас3',
                'cuisine_type': 'Итальянская',
                'avg_check': 2450,
                'working_hours': '12:00 - 00:00',
                'description': 'A Taste of Perfection. Итальянская кухня высшего уровня в самом сердце Москвы.',
                'phone': '+74951234567',
                'overall_rating': 4.8,
                'total_reviews': 287,
            },
            {
                'name': 'Хитч',
                'slug': 'hitch',
                'city': 'Санкт-Петербург',
                'address': 'Санкт-Петербург, Московский проспект, 179',
                'cuisine_type': 'Европейская, русская',
                'avg_check': 2640,
                'working_hours': '10:00 - 00:00',
                'description': 'Современный мясной ресторан с собственной культурой мяса. Брутальные завтраки и изысканные обеды.',
                'phone': '+78121234567',
                'overall_rating': 4.7,
                'total_reviews': 245,
            },
            {
                'name': 'Турандот',
                'slug': 'turandot',
                'city': 'Москва',
                'address': 'Москва, Тверской бульвар, 3',
                'cuisine_type': 'Европейская, русская',
                'avg_check': 3200,
                'working_hours': '11:00 - 00:00',
                'description': 'Роскошный ресторан в центре Москвы с авторской кухней и волшебной атмосферой.',
                'phone': '+74959876543',
                'overall_rating': 4.9,
                'total_reviews': 512,
            },
            {
                'name': 'Savoy',
                'slug': 'savoy',
                'city': 'Москва',
                'address': 'Москва, ул. Петровка, 2',
                'cuisine_type': 'Итальянская',
                'avg_check': 2800,
                'working_hours': '12:00 - 02:00',
                'description': 'Изысканная итальянская кухня в историческом здании. Паста, ризотто и лучшие вина.',
                'phone': '+74955553322',
                'overall_rating': 4.6,
                'total_reviews': 189,
            },
        ]
        
        created_restaurants = []
        for data in restaurants_data:
            restaurant, created = Restaurant.objects.get_or_create(
                slug=data['slug'],
                defaults={**data, 'owner': owner_profile}
            )
            created_restaurants.append(restaurant)
            status = '✅ Создан' if created else '⏭️ Уже существует'
            self.stdout.write(f'{status}: {restaurant.name}')
        
        # ==========================================
        # 3. Создаём персонал для White Rabbit
        # ==========================================
        white_rabbit = created_restaurants[0]
        
        staff_data = [
            {
                'full_name': 'Александр Петров',
                'position': 'chef',
                'experience_years': 12,
                'csat_score': 95,
                'reviews_count': 89,
                'badges_count': 23,
                'tips_total': 125000,
            },
            {
                'full_name': 'Анастасия Савичева',
                'position': 'waiter',
                'experience_years': 3,
                'csat_score': 92,
                'reviews_count': 45,
                'badges_count': 15,
                'tips_total': 78000,
            },
            {
                'full_name': 'Николай Востриков',
                'position': 'bartender',
                'experience_years': 5,
                'csat_score': 88,
                'reviews_count': 32,
                'badges_count': 8,
                'tips_total': 56000,
            },
        ]
        
        for data in staff_data:
            staff, created = StaffMember.objects.get_or_create(
                restaurant=white_rabbit,
                full_name=data['full_name'],
                defaults=data
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'✅ Сотрудник: {staff.full_name}'))
        
        # ==========================================
        # 4. Создаём меню для White Rabbit
        # ==========================================
        menu, _ = Menu.objects.get_or_create(
            restaurant=white_rabbit,
            name='Основное меню',
            defaults={'is_active': True}
        )
        
        # Категории
        categories_data = [
            ('Салаты', 1),
            ('Паста', 2),
            ('Мясо', 3),
            ('Десерты', 4),
        ]
        
        created_categories = {}
        for name, order in categories_data:
            cat, _ = MenuCategory.objects.get_or_create(
                menu=menu,
                name=name,
                defaults={'sort_order': order}
            )
            created_categories[name] = cat
        
        # Блюда
        menu_items_data = [
            {
                'category': 'Салаты',
                'name': 'Цезарь с креветками',
                'description': 'Романо, тигровые креветки, пармезан, гренки, соус Цезарь',
                'price': 750,
                'is_new': True,
            },
            {
                'category': 'Паста',
                'name': 'Карбонара Классика',
                'description': 'Спагетти с беконом, пармезаном, яичным желтком и чёрным перцем',
                'price': 890,
                'is_popular': True,
            },
            {
                'category': 'Мясо',
                'name': 'Оссобуко по-милански',
                'description': 'Томлёная телячья голень с гремолата и ризотто',
                'price': 1450,
                'is_popular': True,
                'is_chef_recommended': True,
            },
            {
                'category': 'Десерты',
                'name': 'Тирамису',
                'description': 'Классический итальянский десерт с маскарпоне и эспрессо',
                'price': 590,
                'is_popular': True,
            },
        ]
        
        for item_data in menu_items_data:
            category = created_categories[item_data.pop('category')]
            MenuItem.objects.get_or_create(
                category=category,
                name=item_data['name'],
                defaults=item_data
            )
        
        self.stdout.write(self.style.SUCCESS('✅ Меню создано для White Rabbit'))
        
        # ==========================================
        # 5. Создаём отзывы
        # ==========================================
        # Гость для отзывов
        guest_user, _ = User.objects.get_or_create(
            username='+79032743037',
            defaults={'first_name': 'Александр', 'last_name': 'Петров'}
        )
        
        reviews_data = [
            {
                'restaurant': white_rabbit,
                'user': guest_user,
                'rating': 5,
                'text': 'Превосходный ресторан! Паста карбонара — лучшая, что я пробовал в Москве. Отличное обслуживание и уютная атмосфера. Обязательно вернусь!',
            },
            {
                'restaurant': white_rabbit,
                'rating': 4,
                'text': 'Очень вкусно, но немного долго готовили. В целом остались довольны, обязательно вернёмся ещё раз. Тирамису просто божественный!',
            },
        ]
        
        for data in reviews_data:
            user = data.pop('user', None)
            Review.objects.get_or_create(
                restaurant=data['restaurant'],
                text=data['text'],
                defaults={**data, 'user': user, 'is_moderated': True}
            )
        
        self.stdout.write(self.style.SUCCESS('✅ Отзывы созданы'))
        
        # ==========================================
        # ФИНАЛ
        # ==========================================
        self.stdout.write(self.style.SUCCESS('\n🎉 База данных успешно наполнена!'))
        self.stdout.write(self.style.SUCCESS('👉 Открой http://127.0.0.1:8000 и увидишь рестораны!'))