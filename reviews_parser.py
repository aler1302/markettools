import json

def get_demo_reviews():
    """Возвращает демо-отзывы для тестирования"""
    return {
        'success': True,
        'reviews': [
            {
                'author': 'Анна М.',
                'rating': 5,
                'text': 'Отличная подушка! Очень удобная, хорошо поддерживает шею. Сплю теперь без болей.',
                'date': '2026-09-01',
                'pros': 'Удобная, качественная, хорошая поддержка',
                'cons': ''
            },
            {
                'author': 'Игорь К.',
                'rating': 4,
                'text': 'Подушка хорошая, но сначала был запах. Через пару дней выветрился. Спать удобно.',
                'date': '2026-08-30',
                'pros': 'Удобная, качественная',
                'cons': 'Первоначальный запах'
            },
            {
                'author': 'Марина С.',
                'rating': 5,
                'text': 'Наконец-то нашла идеальную подушку! Боли в шее прошли. Рекомендую всем!',
                'date': '2026-08-28',
                'pros': 'Эффективная, удобная',
                'cons': ''
            },
            {
                'author': 'Дмитрий В.',
                'rating': 3,
                'text': 'Подушка нормальная, но для меня слишком высокая. Не всем подойдёт.',
                'date': '2026-08-25',
                'pros': 'Качественная',
                'cons': 'Слишком высокая'
            },
            {
                'author': 'Елена П.',
                'rating': 5,
                'text': 'Превосходно! Мемори-форма отлично работает. Шея не болит.',
                'date': '2026-08-22',
                'pros': 'Мемори-форма, поддержка, качество',
                'cons': ''
            },
            {
                'author': 'Сергей Л.',
                'rating': 4,
                'text': 'Хорошая подушка за свои деньги. Чехол съёмный это плюс.',
                'date': '2026-08-20',
                'pros': 'Цена, съёмный чехол',
                'cons': ''
            },
            {
                'author': 'Ольга Р.',
                'rating': 2,
                'text': 'Не подошла. Слишком жёсткая для меня. Вернула.',
                'date': '2026-08-18',
                'pros': '',
                'cons': 'Жёсткая, не всем подходит'
            },
            {
                'author': 'Александр Т.',
                'rating': 5,
                'text': 'Отличная покупка! Сплю как младенец. Боли прошли.',
                'date': '2026-08-15',
                'pros': 'Комфорт, поддержка шеи',
                'cons': ''
            }
        ],
        'total': 8
    }


def parse_manual_reviews(reviews_text):
    """
    Парсит отзывы из текста (копипаст с сайта)
    """
    reviews = []
    
    # Простая эвристика для разделения отзывов
    lines = reviews_text.strip().split('\n\n')
    
    for line in lines:
        if line.strip():
            reviews.append({
                'author': 'Пользователь',
                'rating': 4,
                'text': line.strip(),
                'date': '',
                'pros': '',
                'cons': ''
            })
    
    return {
        'success': True if reviews else False,
        'reviews': reviews,
        'total': len(reviews)
    }


def analyze_reviews_with_gpt(reviews, product_name=""):
    """
    Анализирует отзывы через YandexGPT
    """
    
    from yandex_gpt import API_KEY, FOLDER_ID
    import requests as req
    
    # Формируем текст отзывов для анализа
    reviews_text = ""
    for i, review in enumerate(reviews[:30], 1):
        reviews_text += f"""
Отзыв {i}:
Оценка: {review['rating']}/5
Текст: {review['text'][:300]}
Плюсы: {review.get('pros', '')}
Минусы: {review.get('cons', '')}
---
"""
    
    prompt = f"""Ты — аналитик отзывов о товарах на маркетплейсах.

Проанализируй отзывы о товаре: {product_name if product_name else "товар"}

ОТЗЫВЫ:
{reviews_text}

Создай подробный отчёт в формате JSON:

{{
    "summary": {{
        "total_reviews": {len(reviews)},
        "average_rating": 4.2,
        "positive_percentage": 80,
        "negative_percentage": 10
    }},
    "pros": [
        "самое частое преимущество 1",
        "самое частое преимущество 2",
        "самое частое преимущество 3",
        "самое частое преимущество 4",
        "самое частое преимущество 5"
    ],
    "cons": [
        "самая частая проблема 1",
        "самая частая проблема 2",
        "самая частая проблема 3",
        "самая частая проблема 4",
        "самая частая проблема 5"
    ],
    "customer_pain_points": [
        "боль клиентов 1 (что не нравится)",
        "боль клиентов 2",
        "боль клиентов 3"
    ],
    "recommendations": [
        "рекомендация для улучшения 1",
        "рекомендация для улучшения 2",
        "рекомендация для улучшения 3"
    ],
    "target_audience": "описание целевой аудитории (кто покупает)",
    "competitor_advantages": "что можно улучшить по сравнению с конкурентами"
}}

ВАЖНО:
1. Верни ТОЛЬКО JSON без дополнительных комментариев
2. НЕ используй markdown (**, #, ```json)
3. Анализируй реальные отзывы
4. Выяви настоящие боли клиентов
5. Дай конкретные рекомендации
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
    
    headers_req = {
        'Content-Type': 'application/json',
        'Authorization': f'Api-Key {API_KEY}'
    }
    
    response = req.post(
        'https://llm.api.cloud.yandex.net/foundationModels/v1/completion',
        json=data,
        headers=headers_req
    )
    
    result = response.json()
    
    if 'result' in result and 'alternatives' in result['result']:
        generated_text = result['result']['alternatives'][0]['message']['text']
        
        # Очищаем от markdown
        generated_text = generated_text.replace('```json', '').replace('```', '').strip()
        
        # Ищем JSON
        start_idx = generated_text.find('{')
        end_idx = generated_text.rfind('}')
        
        if start_idx != -1 and end_idx != -1:
            json_text = generated_text[start_idx:end_idx+1]
            
            try:
                analysis = json.loads(json_text)
                return {
                    'success': True,
                    'analysis': analysis,
                    'reviews_count': len(reviews)
                }
            except json.JSONDecodeError as e:
                return {
                    'success': False,
                    'error': f"Ошибка парсинга JSON: {str(e)}",
                    'raw_text': generated_text[:500]
                }
    
    return {
        'success': False,
        'error': f"Ошибка API: {result}"
    }