import requests
import json

API_KEY = "AQVNyvtoF3eCbjVg7SPPABfos_qaeenkk7nHd6ro"
FOLDER_ID = "b1gqmeqefi15ih83tckh"

def generate_title(product_name, product_features, marketplace="Wildberries"):
    """Генерирует SEO-оптимизированное название товара"""
    
    prompt = f"""Ты — эксперт по SEO для маркетплейсов {marketplace}.

Создай 5 вариантов продающих названий товара.

Товар: {product_name}
Характеристики: {product_features}

ПРАВИЛА для {marketplace}:
- Длина: 60-100 символов
- Включи главные ключевые слова
- Укажи важные характеристики (размер, материал, цвет)
- Без лишних слов и знаков препинания
- Начинай с главного слова

Верни ТОЛЬКО JSON:

{{
    "titles": [
        "вариант 1",
        "вариант 2",
        "вариант 3",
        "вариант 4",
        "вариант 5"
    ],
    "best_title": "лучший вариант",
    "keywords_used": ["ключ1", "ключ2", "ключ3"]
}}

НЕ используй markdown. Только JSON."""

    data = {
        "modelUri": f"gpt://{FOLDER_ID}/yandexgpt/latest",
        "completionOptions": {
            "stream": False,
            "temperature": 0.7,
            "maxTokens": 1500
        },
        "messages": [{"role": "user", "text": prompt}]
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
        text = result['result']['alternatives'][0]['message']['text']
        text = text.replace('```json', '').replace('```', '').strip()
        
        start = text.find('{')
        end = text.rfind('}')
        
        if start != -1 and end != -1:
            try:
                return json.loads(text[start:end+1])
            except:
                return {"error": "Ошибка парсинга", "raw": text[:300]}
    
    return {"error": "Ошибка API"}