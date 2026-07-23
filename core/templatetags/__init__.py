from django import template

register = template.Library()

@register.filter
def split(value, arg):
    """Разделяет строку по разделителю"""
    return value.split(arg)

@register.filter
def get_item(dictionary, key):
    """Получает значение из словаря по ключу"""
    try:
        return dictionary.get(int(key), 0)
    except (ValueError, TypeError, AttributeError):
        return 0