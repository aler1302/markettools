import requests
import json

API_KEY = "AQVNyvtoF3eCbjVg7SPPABfos_qaeenkk7nHd6ro"
FOLDER_ID = "b1gqmeqefi15ih83tckh"

def generate_product_card(product_name, product_features, target_audience=""):
    """Генерирует полную карточку товара для маркетплейса в формате JSON"""
    
    prompt = """Ты — профессиональный копирайтер для маркетплейсов Wildberries и Ozon.

Твоя задача — создать структурированную карточку товара в формате JSON.

ТОВАР: """ + product_name + """
ХАРАКТЕРИСТИКИ: """ + product_features + """
ЦЕЛЕВАЯ АУДИТОРИЯ: """ + (target_audience if target_audience else "широкая аудитория") + """

Верни ТОЛЬКО JSON объект в следующем формате:

{
    "title": "Продающий заголовок товара (до 100 символов)",
    "description": "Подробное SEO-оптимизированное описание (300-500 символов). Опиши преимущества, характеристики, для кого подходит. Пиши продающим текстом.",
    "advantages": [
        "Преимущество 1 (3-7 слов)",
        "Преимущество 2 (3-7 слов)",
        "Преимущество 3 (3-7 слов)",
        "Преимущество 4 (3-7 слов)",
        "Преимущество 5 (3-7 слов)",
        "Преимущество 6 (3-7 слов)"
    ],
    "characteristics": [
        "Характеристика 1",
        "Характеристика 2",
        "Характеристика 3",
        "Характеристика 4",
        "Характеристика 5"
    ],
    "keywords": [
        "ключевое слово 1",
        "ключевое слово 2",
        "ключевое слово 3",
        "ключевое слово 4",
        "ключевое слово 5",
        "ключевое слово 6",
        "ключевое слово 7",
        "ключевое слово 8",
        "ключевое слово 9",
        "ключевое слово 10"
    ],
    "infographic": [
        "Текст для блока 1 инфографики (главное преимущество)",
        "Текст для блока 2 инфографики (характеристики)",
        "Текст для блока 3 инфографики (преимущества использования)",
        "Текст для блока 4 инфографики (для кого подходит)",
        "Текст для блока 5 инфографики (призыв к покупке)"
    ]
}

ВАЖНО:
1. Верни ТОЛЬКО JSON без дополнительных комментариев
2. НЕ используй markdown (**, #, ```json)
3. Все тексты на русском языке
4. Используй продающие формулировки
5. Добавляй эмодзи где уместно ( ✅ ⭐ 🔥 💯)
"""

    data = {
        "modelUri": f"gpt://{FOLDER_ID}/yandexgpt/latest",
        "completionOptions": {
            "stream": False,
            "temperature": 0.7,
            "maxTokens": 2000
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
        generated_text = result['result']['alternatives'][0]['message']['text']
        
        # Очищаем от markdown и лишних символов
        generated_text = generated_text.replace('```json', '').replace('```', '').strip()
        
        # Ищем JSON в тексте (между { и })
        start_idx = generated_text.find('{')
        end_idx = generated_text.rfind('}')
        
        if start_idx != -1 and end_idx != -1:
            json_text = generated_text[start_idx:end_idx+1]
            
            try:
                card_data = json.loads(json_text)
                return card_data
            except json.JSONDecodeError as e:
                return {
                    "error": f"Ошибка парсинга JSON: {str(e)}",
                    "raw_text": generated_text[:500]
                }
        else:
            return {
                "error": "JSON не найден в ответе",
                "raw_text": generated_text[:500]
            }
    else:
        return {"error": f"Ошибка API: {result}"}