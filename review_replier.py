import requests
import json

API_KEY = "AQVNyvtoF3eCbjVg7SPPABfos_qaeenkk7nHd6ro"
FOLDER_ID = "b1gqmeqefi15ih83tckh"

def generate_reply(review_text, rating, product_name=""):
    """Генерирует ответ на отзыв покупателя"""
    
    rating_text = "положительный" if rating >= 4 else ("нейтральный" if rating == 3 else "отрицательный")
    
    prompt = f"""Ты — менеджер по работе с клиентами маркетплейса.

Напиши вежливый и профессиональный ответ на {rating_text} отзыв (оценка {rating}/5).

Товар: {product_name if product_name else "наш товар"}
Отзыв покупателя: "{review_text}"

ПРАВИЛА:
1. Поблагодари за отзыв
2. Если положительный — вырази радость
3. Если отрицательный — извинись и предложи решение
4. Будь вежливым и профессиональным
5. Длина: 2-4 предложения
6. НЕ используй шаблонные фразы
7. Пиши от лица магазина

Верни ТОЛЬКО JSON:

{{
    "reply": "текст ответа",
    "tone": "дружелюбный/профессиональный/сочувствующий"
}}

НЕ используй markdown. Только JSON."""

    data = {
        "modelUri": f"gpt://{FOLDER_ID}/yandexgpt/latest",
        "completionOptions": {
            "stream": False,
            "temperature": 0.6,
            "maxTokens": 800
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


def generate_bulk_replies(reviews, product_name=""):
    """Генерирует ответы на несколько отзывов"""
    replies = []
    for review in reviews[:10]:
        result = generate_reply(
            review.get('text', ''),
            review.get('rating', 5),
            product_name
        )
        replies.append({
            'review': review.get('text', '')[:100],
            'rating': review.get('rating', 5),
            'reply': result.get('reply', 'Ошибка генерации'),
            'tone': result.get('tone', '')
        })
    return replies