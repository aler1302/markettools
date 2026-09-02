import requests
import json

# Твой API-ключ
API_KEY = "AQVNyvtoF3eCbjVg7SPPABfos_qaeenkk7nHd6ro"

# ПРАВИЛЬНЫЙ Folder ID (из адресной строки)
FOLDER_ID = "b1gqmeqefi15ih83tckh"

def generate_description(product_info):
    """Генерирует SEO-описание через YandexGPT"""
    
    prompt = f"""Создай SEO-оптимизированное описание товара для маркетплейса (Ozon/Wildberries).

Товар: {product_info}

Требования:
- Используй ключевые слова
- Добавь эмодзи где уместно
- Структурируй текст (абзацы, списки)
- Выдели преимущества
- Длина: 500-800 символов
- Пиши на русском языке, продающим стилем

Описание:"""

    data = {
        "modelUri": f"gpt://{FOLDER_ID}/yandexgpt/latest",
        "completionOptions": {
            "stream": False,
            "temperature": 0.7,
            "maxTokens": 1000
        },
        "messages": [
            {
                "role": "user",
                "text": prompt
            }
        ]
    }
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Api-Key {API_KEY}'
    }
    
    response = requests.post(
        'https://llm.api.cloud.yandex.net/foundationModels/v1/completion',
        json=data,
        headers=headers
    )
    
    result = response.json()
    
    if 'result' in result and 'alternatives' in result['result']:
        description = result['result']['alternatives'][0]['message']['text']
        return description
    else:
        return f"Ошибка API: {result}"