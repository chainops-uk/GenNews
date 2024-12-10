from tqdm import tqdm
from datetime import datetime
import json
import time
import asyncio
import aiohttp

from ..api import (
    generate_questions_pool,
    generate_questions_ollama_parallel,
    generate_questions_batch_ollama_async,
    create_fred_context,
    create_acled_context,
    create_crypto_context,
    create_prompt,
    get_system_prompt
)
from ..utils import deduplicate_questions
from ..utils.cache import save_questions_cache, load_questions_cache

def generate_questions(news_headlines, fred_data, acled_data, crypto_data=None, *, total_questions=30, client=None, model='gpt4', 
                      batch_size=30, max_retries=3, cache_dir=None, parallel=False,
                      market_data=None):
    """Generate questions with batching support."""
    # Определяем требуемые категории
    required_categories = []
    
    # Добавляем категории на основе доступных данных
    if fred_data:
        required_categories.append('economic_indicator')
    if acled_data and acled_data.get('countries'):
        required_categories.append('social_events')
    if crypto_data:
        required_categories.append('cryptocurrency')
    if market_data:
        required_categories.append('financial_market')
    
    if not required_categories:
        print("Error: No valid data sources available")
        return []
    
    print(f"\nGenerating questions for categories: {', '.join(required_categories)}")
    
    if model == 'llama2':
        if parallel:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(
                generate_questions_ollama_parallel(
                    news_headlines,
                    fred_data,
                    acled_data,
                    crypto_data,
                    total_questions,
                    batch_size=5,
                    required_categories=required_categories,
                    market_data=market_data
                )
            )
        else:
            # Генерируем большой пул вопросов и выбираем самые разнообразные
            pool_size = max(200, total_questions * 4)  # Увеличиваем размер пула
            print(f"\nGenerating pool of {pool_size} questions...")
            
            questions = generate_questions_pool(
                news_headlines,
                fred_data,
                acled_data,
                crypto_data,
                total_questions,
                pool_size=pool_size,
                required_categories=required_categories,
                market_data=market_data
            )
            
            # Сохраняем в кэш для анализа
            if cache_dir:
                save_questions_cache(questions, cache_dir)
            
            return questions
    else:  # gpt4, gpt3.5, gpt4-turbo
        return generate_questions_batch_gpt4(
            news_headlines,
            fred_data,
            acled_data,
            crypto_data,
            total_questions,
            client,
            required_categories=required_categories,
            model=model
        )

def generate_questions_batch_gpt4(news_headlines, fred_data, acled_data, crypto_data, num_questions, client, required_categories=None, model='gpt4'):
    """Generate a batch of questions using GPT models."""
    fred_context = create_fred_context(fred_data)
    acled_context = create_acled_context(acled_data)
    crypto_context = create_crypto_context(crypto_data) if crypto_data else ""
    
    # Добавляем информацию о требуемых категориях в промпт
    if required_categories:
        categories_str = ", ".join(required_categories)
        extra_prompt = f"\nIMPORTANT: Generate questions ONLY for these categories: {categories_str}"
    else:
        extra_prompt = ""
    
    prompt = create_prompt(num_questions, fred_context, acled_context, crypto_context, news_headlines) + extra_prompt
    
    max_retries = 3
    retry_delay = 60  # seconds
    
    # Определяем параметры модели
    model_params = {
        'gpt4': {
            'name': 'gpt-4',
            'max_tokens': 4000,
            'temperature': 0.7
        },
        'gpt3.5': {
            'name': 'gpt-3.5-turbo',
            'max_tokens': 4000,
            'temperature': 0.7
        },
        'gpt4-turbo': {
            'name': 'gpt-4-1106-preview',
            'max_tokens': 4000,
            'temperature': 0.7
        }
    }
    
    # Получаем параметры текущей модели
    model_config = model_params.get(model, model_params['gpt4'])
    
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model_config['name'],
                messages=[
                    {"role": "system", "content": get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=model_config['max_tokens'],
                temperature=model_config['temperature']
            )
            
            content = response.choices[0].message.content.strip()
            
            # Попытка очистить контент от лишних символов
            if not content.startswith('['):
                content = content[content.find('['):]
            if not content.endswith(']'):
                content = content[:content.rfind(']')+1]
                
            try:
                questions = json.loads(content)
            except json.JSONDecodeError as e:
                print(f"JSON parsing error: {e}")
                print("Response content:", content[:200])
                continue
                
            # Validate questions
            validated_questions = validate_questions(questions)
            
            if validated_questions:
                return validated_questions
            else:
                print("No valid questions in response. Retrying...")
                continue

        except Exception as e:
            print(f"Error generating questions: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                return []
    
    return []

def validate_questions(questions):
    """Validate a list of questions."""
    valid_questions = []
    used_questions = set()
    
    for question in questions:
        try:
            # Проверяем обязательные поля
            if not all(key in question for key in ['question', 'timeframe', 'category', 'metric', 'target_value']):
                continue
            
            # Проверяем уникальность
            if question['question'] in used_questions:
                continue
            
            # Проверяем формат даты
            try:
                date = datetime.strptime(question['timeframe'], '%Y/%m/%d')
                if not (datetime(2024, 12, 1) <= date <= datetime(2025, 6, 30)):
                    continue
            except ValueError:
                continue
            
            # Проверяем значения
            try:
                value = float(question['target_value'])
                if question['category'] == 'social_events' and not (50 <= value <= 500):
                    continue
                elif question['category'] == 'economic_indicator':
                    if question['metric'] == 'unemployment_rate' and not (2.0 <= value <= 10.0):
                        continue
            except (ValueError, TypeError):
                continue
            
            # Добавляем валидный вопрос
            used_questions.add(question['question'])
            valid_questions.append(question)
            
        except Exception as e:
            print(f"Error validating question: {str(e)}")
            continue
    
    return valid_questions

async def generate_questions_batch_gpt4_async(news_headlines, fred_data, acled_data, crypto_data, num_questions, client):
    """Асинхронная генерация вопросов через GPT-4."""
    tasks = []
    batch_size = min(5, num_questions)  # Разбиваем на маленькие батчи
    for i in range(0, num_questions, batch_size):
        task = asyncio.create_task(
            generate_questions_batch_gpt4(
                news_headlines, 
                fred_data, 
                acled_data,
                crypto_data,
                min(batch_size, num_questions - i), 
                client
            )
        )
        tasks.append(task)
    
    results = await asyncio.gather(*tasks)
    all_questions = []
    for batch in results:
        all_questions.extend(batch)
    return all_questions

def validate_single_question(question):
    """Validate a single question."""
    try:
        # Check required fields
        required_fields = ['question', 'timeframe', 'category', 'metric', 'measurement_source', 'target_value']
        if not all(field in question for field in required_fields):
            print(f"Missing required fields. Found: {list(question.keys())}")
            return False

        # Check and clean timeframe
        timeframe = question['timeframe']
        if ' to ' in timeframe or ' and ' in timeframe:
            print(f"Invalid timeframe format (contains range): {timeframe}")
            return False
        
        try:
            date = datetime.strptime(timeframe, '%Y/%m/%d')
            if not (datetime(2024, 12, 1) <= date <= datetime(2025, 6, 30)):
                print(f"Invalid timeframe (out of range): {timeframe}")
                return False
        except ValueError:
            print(f"Invalid timeframe format: {timeframe}")
            return False

        # Valid metrics and sources
        valid_metrics = {
            'cryptocurrency': [
                'price_target',
                'market_cap',
                'volume_24h',
                'price_change',
                'market_cap_change'
            ],
            'social_events': [
                'protest_count',
                'fatalities',
                'event_frequency',
                'violence_incidents',
                'riot_count'
            ],
            'economic_indicator': [
                'gdp_growth_rate',
                'inflation_rate',
                'unemployment_rate',
                'interest_rate',
                'treasury_rate',
                'cpi_change'
            ]
        }

        valid_sources = {
            'cryptocurrency': [
                'CoinMarketCap',
                'Binance',
                'CoinGecko'
            ],
            'social_events': [
                'ACLED database'
            ],
            'economic_indicator': [
                'BEA initial GDP release',
                'BLS initial CPI release',
                'Federal Reserve',
                'FRED database'
            ]
        }

        # Check category
        category = question['category']
        if category not in valid_metrics:
            print(f"Invalid category: {category}")
            return False

        # Check metric
        metric = question['metric'].lower().strip()
        valid_category_metrics = [m.lower() for m in valid_metrics[category]]
        if metric not in valid_category_metrics:
            print(f"Invalid metric for category {category}: {metric}")
            print(f"Valid metrics are: {', '.join(valid_metrics[category])}")
            return False

        # Check source
        source = question['measurement_source']
        if source not in valid_sources[category]:
            print(f"Invalid source for category {category}: {source}")
            print(f"Valid sources are: {', '.join(valid_sources[category])}")
            return False

        # Check target_value
        try:
            if isinstance(question['target_value'], str):
                # Clean the string value
                value = question['target_value'].replace('$', '').replace('%', '').replace(',', '').strip()
                question['target_value'] = float(value)
            elif not isinstance(question['target_value'], (int, float)):
                print(f"Invalid target_value type: {type(question['target_value'])}")
                return False
        except (ValueError, TypeError):
            print(f"Invalid target_value: {question['target_value']}")
            return False

        # Check question format
        if not question['question'].startswith('Will '):
            print("Question must start with 'Will'")
            return False

        return True
    except Exception as e:
        print(f"Validation error: {str(e)}")
        return False
