"""
Сервис отправки SMS через SMS.ru
"""
import random
import string
import requests
from django.conf import settings


def generate_code(length=4):
    """Генерирует случайный 4-значный код"""
    return ''.join(random.choices(string.digits, k=length))


def send_sms_code(phone: str, code: str) -> dict:
    """
    Отправляет SMS с кодом подтверждения через SMS.ru.
    Возвращает {'success': True/False, 'message': '...'}
    """
    api_id = settings.SMS_RU_API_ID
    
    # Если API ключ не настроен, работаем в демо-режиме (вывод в консоль)
    if not api_id or api_id == 'ВАШ_API_ID_СЮДА':
        print(f"\n{'='*50}")
        print(f"📱 ДЕМО-РЕЖИМ: SMS на {phone}")
        print(f"🔐 Код подтверждения: {code}")
        print(f"{'='*50}\n")
        return {'success': True, 'message': 'Код выведен в консоль (SMS.ru не настроен)'}
    
    # Реальная отправка через SMS.ru
    try:
        url = 'https://sms.ru/sms/send'
        params = {
            'api_id': api_id,
            'to': phone,
            'msg': f'БезЛука: ваш код подтверждения {code}. Не сообщайте его никому.',
            'json': 1,
        }
        
        response = requests.post(url, data=params, timeout=10)
        data = response.json()
        
        if data.get('status') == 'OK':
            return {'success': True, 'message': 'SMS отправлено'}
        else:
            error_msg = data.get('message', 'неизвестная ошибка')
            return {'success': False, 'message': f'Ошибка SMS.ru: {error_msg}'}
    
    except requests.exceptions.Timeout:
        return {'success': False, 'message': 'Превышено время ожидания'}
    except requests.exceptions.RequestException as e:
        return {'success': False, 'message': f'Ошибка сети: {str(e)}'}
    except Exception as e:
        return {'success': False, 'message': f'Неизвестная ошибка: {str(e)}'}