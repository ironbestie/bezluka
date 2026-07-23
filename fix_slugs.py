import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from core.models import Restaurant
import uuid

for r in Restaurant.objects.filter(slug=''):
    r.slug = f"rest-{uuid.uuid4().hex[:8]}"
    r.save()
    print(f"Исправлен: {r.name}")

print("Готово!")