import httpx
import ollama
from datetime import datetime, timedelta
import json
import time
import asyncio
import aiohttp
from .crypto_client import create_crypto_context
import re
import traceback
from .eodhd_client import create_market_context
import random
from collections import defaultdict
from contextlib import contextmanager
import signal

def get_system_prompt():
    """Get system prompt for question generation."""
    return (
        "You are a financial analyst. Generate diverse questions about different topics using this EXACT format:\n\n"
        "For cryptocurrency questions:\n"
        '{"question": "Will [coin] price exceed [X] by [date]?",\n'
        ' "timeframe": "YYYY/MM/DD",\n'
        ' "category": "cryptocurrency",\n'
        ' "metric": "price_target",\n'
        ' "target_value": [reasonable price based on current price],\n'
        ' "measurement_source": "CoinMarketCap"}\n\n'
        "For economic questions:\n"
        '{"question": "Will [indicator] [change] to [X] by [date]?",\n'
        ' "timeframe": "YYYY/MM/DD",\n'
        ' "category": "economic_indicator",\n'
        ' "metric": "unemployment_rate",\n'
        ' "target_value": [reasonable value between 2.0 and 10.0],\n'
        ' "measurement_source": "FRED database"}\n\n'
        "For social questions:\n"
        '{"question": "Will protest count in [country] exceed [X] by [date]?",\n'
        ' "timeframe": "YYYY/MM/DD",\n'
        ' "category": "social_events",\n'
        ' "metric": "protest_count",\n'
        ' "target_value": [value between 50 and 500],\n'
        ' "measurement_source": "ACLED database"}\n\n'
        "For market questions:\n"
        '{"question": "Will [stock] price exceed [X] by [date]?",\n'
        ' "timeframe": "YYYY/MM/DD",\n'
        ' "category": "financial_market",\n'
        ' "metric": "price_target",\n'
        ' "target_value": [reasonable price based on current price],\n'
        ' "measurement_source": "EOD Historical Data"}\n\n'
        "IMPORTANT RULES:\n"
        "1. Use ONLY these exact categories and sources\n"
        "2. Generate diverse questions about different topics\n"
        "3. Use dates between 2024/12/01 and 2025/06/30\n"
        "4. Use reasonable target values based on current data\n"
        "5. Do not repeat similar questions\n"
        "6. Include relevant news context in questions"
    )

def create_prompt(num_questions, fred_context, acled_context, crypto_context, news_headlines, market_context=""):
    """Create prompt for question generation."""
    prompt = (
        f"Generate {num_questions} questions in a SINGLE JSON array like this:\n\n"
        "[\n"
        "  {\n"
        '    "question": "Will Bitcoin price exceed 100000 by 2025/03/31?",\n'
        '    "timeframe": "2025/03/31",\n'
        '    "category": "cryptocurrency",\n'
        '    "metric": "price_target",\n'
        '    "target_value": 100000,\n'
        '    "measurement_source": "CoinMarketCap"\n'
        "  },\n"
        "  {\n"
        '    "question": "Will unemployment rate drop below 4.5 by 2025/03/31?",\n'
        '    "timeframe": "2025/03/31",\n'
        '    "category": "economic_indicator",\n'
        '    "metric": "unemployment_rate",\n'
        '    "target_value": 4.5,\n'
        '    "measurement_source": "FRED database"\n'
        "  }\n"
        "]\n\n"
        "IMPORTANT: Put ALL questions in ONE array. Do not create multiple arrays.\n\n"
        "USE THIS DATA:\n"
        f"ECONOMIC DATA: {fred_context}\n"
        f"SOCIAL DATA: {acled_context}\n"
        f"CRYPTO DATA: {crypto_context}\n"
        f"MARKET DATA: {market_context}\n"
        "RECENT NEWS:\n"
    )
    headlines = news_headlines[:3]
    prompt += '\n'.join(f"- {headline}" for headline in headlines)
    return prompt

def create_fred_context(fred_data):
    """Create context string from FRED data."""
    fred_context = "Current Economic Indicators:\n"
    for indicator, data in fred_data.items():
        if data['latest_value'] is not None:
            fred_context += f"- {data['description']}: {data['latest_value']:.2f} {data['units']}"
            if data['yoy_change'] is not None:
                fred_context += f" (YoY change: {data['yoy_change']:.1f}%)"
            fred_context += "\n"
    return fred_context

def create_acled_context(acled_data):
    """Create context string from ACLED data."""
    context = "Recent Social and Political Events:\n"
    
    if not isinstance(acled_data, dict):
        print("Warning: Invalid ACLED data format")
        return context
    
    # Add summary statistics
    if 'summary' in acled_data and isinstance(acled_data['summary'], dict):
        summary = acled_data['summary']
        if 'total_events' in summary:
            context += f"Total Events: {summary['total_events']}\n"
        if 'total_fatalities' in summary:
            context += f"Total Fatalities: {summary['total_fatalities']}\n"
        
        # Add event type breakdown
        if 'event_types' in summary:
            context += "\nEvent Types:\n"
            for event_type, count in summary['event_types'].items():
                context += f"- {event_type}: {count} events\n"
    
    # Add country information
    if 'countries' in acled_data:
        context += "\nMonitored Countries:\n"
        for country in acled_data['countries']:
            context += f"- {country}\n"
    
    return context

def get_crypto_price_range(crypto_data, symbol):
    """Get reasonable price range for cryptocurrency."""
    if symbol not in crypto_data:
        return 1, 200000  # Default range for unknown crypto
    
    current_price = float(crypto_data[symbol]['price'])
    # Set reasonable price ranges based on current price
    min_price = current_price * 0.5  # 50% below current
    max_price = current_price * 2.0  # 200% above current
    return min_price, max_price

def get_category_prompt(category, context, crypto_data=None, countries=None):
    """Get category-specific prompt."""
    if category == 'cryptocurrency':
        # Создаем список доступных криптовалют с их текущими ценами
        crypto_list = []
        for symbol, data in crypto_data.items():
            price = float(data['price'])
            crypto_list.append(
                f"{data['name']} ({symbol}): current price ${price:.2f}, "
                f"valid range ${price*0.5:.2f} - ${price*2.0:.2f}"
            )
        
        return (
            "Generate ONE unique cryptocurrency price prediction question.\n"
            f"Crypto Data: {context}\n"
            "Available cryptocurrencies and valid price ranges:\n"
            f"{chr(10).join(crypto_list)}\n\n"
            "Use EXACTLY this format and ONLY these cryptocurrencies:\n"
            '{"question": "Will [coin] price [exceed/fall below] [price] by [date]?",\n'
            ' "timeframe": "YYYY/MM/DD",\n'
            ' "category": "cryptocurrency",\n'
            ' "metric": "price_target",\n'
            ' "target_value": [price within valid range],\n'
            ' "measurement_source": "CoinMarketCap"}'
        )
    elif category == 'social_events':
        country_list = ", ".join(countries) if countries else "any country"
        return (
            "Generate ONE unique protest count question.\n"
            f"Social Data: {context}\n"
            f"Use ONLY these country codes: {country_list}\n"
            "Use EXACTLY this format:\n"
            '{"question": "Will protest count in [country_code] exceed [number] by [date]?",\n'
            ' "timeframe": "2025/03/15",\n'  # Example date
            ' "category": "social_events",\n'
            ' "metric": "protest_count",\n'
            ' "target_value": 150,\n'  # Example value
            ' "measurement_source": "ACLED database"}\n\n'
            f"Example: Will protest count in {countries[0]} exceed 150 by 2025/03/15?"
        )
    elif category == 'economic_indicator':
        return (
            "Generate ONE unique economic indicator question.\n"
            f"Economic Data: {context}\n"
            "Use ONE of these metrics:\n"
            "- GDP (target between 25000 and 35000 billion dollars)\n"
            "- Unemployment rate (target between 2% and 10%)\n"
            "- Inflation rate (target between -2% and 15%)\n"
            "- Interest rate (target between 0% and 10%)\n"
            "- Industrial production (target between 80 and 120)\n"
            "- Consumer Price Index (target between 200 and 400)\n\n"
            "Use EXACTLY this format:\n"
            '{"question": "Will [indicator] [increase/decrease] to [value] by [date]?",\n'
            ' "timeframe": "YYYY/MM/DD",\n'
            ' "category": "economic_indicator",\n'
            ' "metric": "[chosen_metric]",\n'
            ' "target_value": [value_within_range],\n'
            ' "measurement_source": "FRED database"}'
        )
    elif category == 'financial_market':
        return (
            "Generate ONE unique stock market question.\n"
            f"Market Data: {context}\n"
            "Use ONE of these metrics:\n"
            "- price_target (stock price prediction)\n"
            "- volume_target (trading volume prediction)\n"
            "- market_cap_target (market capitalization prediction)\n\n"
            "Use EXACTLY this format:\n"
            '{"question": "Will [stock] [metric] [increase/decrease] to [value] by [date]?",\n'
            ' "timeframe": "YYYY/MM/DD",\n'
            ' "category": "financial_market",\n'
            ' "metric": "[chosen_metric]",\n'
            ' "target_value": [reasonable_value],\n'
            ' "measurement_source": "EOD Historical Data"}'
        )

def validate_target_value(category, value, crypto_data=None, question=None):
    """Validate target value is within reasonable range."""
    try:
        value = float(value)
        if category == 'cryptocurrency':
            if not crypto_data or not question:
                print("Missing crypto data or question for validation")
                return False
            
            for symbol, data in crypto_data.items():
                if symbol in question['question'] or data['name'] in question['question']:
                    min_price = float(data['price']) * 0.5  # 50% below current
                    max_price = float(data['price']) * 2.0  # 200% above current
                    if min_price <= value <= max_price:
                        return True
                    else:
                        print(f"Price {value} is outside reasonable range ({min_price:.2f} - {max_price:.2f}) for {symbol}")
                        return False
            print(f"No matching cryptocurrency found in question: {question['question']}")
            return False
        elif category == 'economic_indicator':
            metric = question.get('metric', '')
            if metric == 'gdp_growth_rate':
                return -5 <= value <= 10  # GDP growth rate range
            elif metric == 'inflation_rate':
                return -2 <= value <= 15  # Inflation rate range
            elif metric == 'unemployment_rate':
                return 2 <= value <= 15  # Unemployment rate range
            elif metric == 'interest_rate':
                return 0 <= value <= 10  # Interest rate range
            elif metric == 'treasury_rate':
                return 0 <= value <= 10  # Treasury rate range
            elif metric == 'cpi_change':
                return -5 <= value <= 15  # CPI change range
        elif category == 'social_events':
            return 50 <= value <= 500  # Protest count range
        elif category == 'financial_market':
            metric = question.get('metric', '')
            if metric == 'price_target':
                return value > 0  # Price must be positive
            elif metric == 'volume_24h':
                return value >= 1000  # Reasonable volume
            elif metric == 'market_cap':
                return value >= 1000000  # Reasonable market cap
        return False
    except (ValueError, TypeError) as e:
        print(f"Error validating target value: {str(e)}")
        return False

def get_metric_variations():
    """Get variations of metrics for each category."""
    return {
        'economic_indicator': [
            'GDP growth rate',
            'Unemployment rate',
            'Inflation rate',
            'Industrial production',
            'Consumer confidence',
            'Retail sales',
            'Housing starts',
            'Trade balance',
            'Federal funds rate',
            'Treasury yield spread'
        ],
        'social_events': [
            'protest_count',
            'riot_count',
            'violence_incidents',
            'demonstration_events',
            'conflict_intensity'
        ],
        'cryptocurrency': [
            'price_target',
            'market_cap',
            'trading_volume',
            'price_volatility',
            'dominance_index'
        ],
        'financial_market': [
            'price_target',
            'volume_target',
            'market_cap_target',
            'pe_ratio',
            'revenue_growth'
        ]
    }

def get_timeframe_variations():
    """Get variations of timeframes."""
    base_dates = [
        '2024/12', '2025/01', '2025/02',
        '2025/03', '2025/04', '2025/05', '2025/06'
    ]
    days = [1, 5, 10, 15, 20, 25, 28]
    return [f"{date}/{str(day).zfill(2)}" for date in base_dates 
            for day in days]

def is_unique_question(question, used_questions, similarity_threshold=0.8):
    """Check if question is unique considering multiple factors."""
    # Создаем ключ уникальности
    unique_key = (
        question['category'],
        question['metric'],
        question['timeframe'],
        str(question['target_value']),
        question.get('country', ''),
        question.get('stock', ''),
        question.get('cryptocurrency', '')
    )
    
    # Проверяем точные дубликаты
    if unique_key in used_questions:
        return False
    
    # Проверяем похожие вопросы
    for used_key in used_questions:
        similarity_count = 0
        total_fields = len(unique_key)
        
        # Сравниваем каждое поле
        for new_val, used_val in zip(unique_key, used_key):
            if new_val == used_val:
                similarity_count += 1
            elif isinstance(new_val, str) and isinstance(used_val, str):
                # Проверяем похожесть строк
                if new_val.lower() in used_val.lower() or used_val.lower() in new_val.lower():
                    similarity_count += 0.5
        
        similarity = similarity_count / total_fields
        if similarity >= similarity_threshold:
            return False
    
    return True

def validate_single_question(question, crypto_data=None, countries=None):
    """Validate a single question."""
    try:
        print(f"\nValidating question: {question}")
        
        # Базовая валидация
        required_fields = ['question', 'timeframe', 'category', 'metric', 'target_value']
        missing_fields = [field for field in required_fields if field not in question]
        if missing_fields:
            print(f"Missing required fields: {missing_fields}")
            return False
            
        # Нормализация названий компаний/активов
        if 'question' in question:
            # Для акций
            question['question'] = re.sub(r'Apple(?:\'s)?(?: Inc\.?)?(?: stock)?(?: price)?', 'Apple (AAPL.US)', question['question'])
            question['question'] = re.sub(r'Microsoft(?:\'s)?(?: Corp\.?)?(?: stock)?(?: price)?', 'Microsoft (MSFT.US)', question['question'])
            
            # Для криптовалют
            if crypto_data:
                for symbol, data in crypto_data.items():
                    pattern = f"{data['name']}(?:\'s)?(?: price)?"
                    replacement = f"{data['name']} ({symbol})"
                    question['question'] = re.sub(pattern, replacement, question['question'])
        
        # Проверка категории
        valid_categories = ['economic_indicator', 'social_events', 'cryptocurrency', 'financial_market']
        if question['category'] not in valid_categories:
            print(f"Invalid category: {question['category']}")
            return False
            
        # Проверка даты
        try:
            timeframe = question['timeframe']
            date = datetime.strptime(timeframe, '%Y/%m/%d')
            min_date = datetime(2024, 12, 1)
            max_date = datetime(2025, 6, 30)
            
            if not (min_date <= date <= max_date):
                print(f"Date {date} outside valid range ({min_date} - {max_date})")
                return False
                
        except ValueError as e:
            print(f"Date parsing error: {e}")
            return False
            
        # Проверка target_value
        try:
            value = float(str(question['target_value']).replace('$', '').replace(',', ''))
            question['target_value'] = value
            
            if question['category'] == 'cryptocurrency' and crypto_data:
                for symbol, data in crypto_data.items():
                    if symbol in question['question']:
                        current_price = float(data['price'])
                        min_price = current_price * 0.5
                        max_price = current_price * 2.0
                        if not (min_price <= value <= max_price):
                            print(f"Crypto price {value} outside range ({min_price:.2f} - {max_price:.2f}) for {symbol}")
                            return False
                            
            elif question['category'] == 'social_events':
                if not (50 <= value <= 500):
                    print(f"Invalid protest count: {value} (must be between 50 and 500)")
                    return False
                    
            elif question['category'] == 'economic_indicator':
                if 'gdp' in question['metric'].lower():
                    if not (20000 <= value <= 50000):
                        print(f"GDP value {value} outside range (20000 - 50000)")
                        return False
                elif 'unemployment' in question['metric'].lower():
                    if not (2 <= value <= 15):
                        print(f"Unemployment rate {value} outside range (2 - 15)")
                        return False
                        
        except (ValueError, TypeError) as e:
            print(f"Error validating target value: {e}")
            return False
            
        # Проверка стран для social_events
        if question['category'] == 'social_events' and countries:
            valid_country = False
            for country in countries:
                if country in question['question'].upper():
                    valid_country = True
                    break
            if not valid_country:
                print(f"No valid country found in question. Valid countries: {', '.join(countries)}")
                return False
                
        print("Question validated successfully")
        return True
        
    except Exception as e:
        print(f"Validation error: {str(e)}")
        traceback.print_exc()
        return False

def generate_questions_pool(news_headlines, fred_data, acled_data, crypto_data, num_questions, pool_size=200, required_categories=None, category_targets=None, market_data=None):
    """Generate a large pool of questions and select the most diverse ones."""
    fred_context = create_fred_context(fred_data)
    acled_context = create_acled_context(acled_data)
    crypto_context = create_crypto_context(crypto_data) if crypto_data else ""
    market_context = create_market_context(market_data) if market_data else ""
    
    # Get allowed countries from ACLED data
    allowed_countries = acled_data.get('countries', [])
    if not allowed_countries:
        print("Warning: No valid countries found in ACLED data")
        if 'social_events' in required_categories:
            required_categories.remove('social_events')
            print("Removed social_events from required categories")
    else:
        print(f"Allowed countries: {', '.join(sorted(allowed_countries))}")
    
    # Validate categories
    if not required_categories:
        print("No valid categories specified")
        return []
    
    # Увеличиваем размер пула для лучшего разнообразия
    pool_size = max(pool_size, num_questions * 4)
    
    # Calculate target questions per category
    if category_targets is None:
        category_targets = {cat: num_questions // len(required_categories) for cat in required_categories}
    
    # Увеличиваем цели для пула
    pool_targets = {cat: target * 4 for cat, target in category_targets.items()}
    
    question_pool = []
    used_questions = set()
    total_attempts = 0
    max_attempts = 3000
    category_counts = {cat: 0 for cat in required_categories}
    
    print("\nStarting pool generation with targets:")
    for cat, target in pool_targets.items():
        print(f"- {cat}: {target} questions")
    
    all_targets_reached = False  # Флаг для отслеживания достижения всех целей
    
    max_retries = 3  # Максимальное количество попыток для одного запроса
    
    while len(question_pool) < pool_size and total_attempts < max_attempts and not all_targets_reached:
        try:
            # Проверяем достижение целей
            targets_reached = True
            for cat, count in category_counts.items():
                if count < pool_targets[cat]:
                    targets_reached = False
                    break
            
            if targets_reached:
                print("\nAll category targets reached!")
                all_targets_reached = True
                break
            
            # ыбираем категорию для следующего вопроса
            needed_categories = [
                cat for cat in required_categories 
                if category_counts[cat] < pool_targets[cat]
            ]
            
            if not needed_categories:
                print("\nAll category targets reached!")
                break
                
            target_category = random.choice(needed_categories)
            
            # Создаем промпт с указанием категории
            current_prompt = create_prompt(1, fred_context, acled_context, crypto_context, news_headlines, market_context)
            current_prompt += f"\n\nIMPORTANT: Generate a question for category: {target_category}"
            
            # Генерируем вопрос с повторными попытками
            response = None
            retry_count = 0
            while retry_count < max_retries:
                try:
                    response = ollama.chat(
                        model='llama3.2:3b',
                        messages=[
                            {'role': 'system', 'content': get_system_prompt()},
                            {'role': 'user', 'content': current_prompt}
                        ],
                        options={
                            'temperature': 0.8,
                            'top_p': 0.9,
                            'top_k': 40,
                            'repeat_penalty': 1.1
                        }
                    )
                    break  # Если успешно, выходим из цикла повторных попыток
                except Exception as e:
                    retry_count += 1
                    if retry_count >= max_retries:
                        print(f"Failed after {max_retries} retries")
                        raise e
                    print(f"Error, retrying ({retry_count}/{max_retries})...")
                    time.sleep(2 * retry_count)  # Увеличиваем паузу с каждой попыткой
            
            if not response:
                continue
                
            content = clean_json_content(response['message']['content'])
            print(f"\nCleaned content: {content[:200]}")  # Debug output
            
            try:
                questions = json.loads(content)
                if not isinstance(questions, list):
                    questions = [questions]
                
                for question in questions:
                    # Validate question
                    if validate_single_question(question, crypto_data, allowed_countries):
                        category = question['category']
                        
                        # Check if we need more questions in this category
                        if category in category_counts:
                            current_count = category_counts[category]
                            target_count = pool_targets[category]
                            
                            if current_count < target_count:
                                # Create unique key for question
                                question_key = (
                                    question['category'],
                                    question['metric'],
                                    question['timeframe'],
                                    str(float(question['target_value']))  # Convert to float then string
                                )
                                
                                # Check if question is unique
                                if question_key not in used_questions:
                                    question_pool.append(question)
                                    used_questions.add(question_key)
                                    category_counts[category] += 1
                                    
                                    print(f"\nAdded {category} question: {question['question']}")
                                    print(f"Pool size: {len(question_pool)}/{pool_size}")
                                    print("\nCategory counts:")
                                    for cat, count in category_counts.items():
                                        print(f"- {cat}: {count}/{pool_targets[cat]}")
                                    
                                    # Check if we've reached all targets
                                    targets_reached = True
                                    for cat, count in category_counts.items():
                                        if count < pool_targets[cat]:
                                            targets_reached = False
                                            break
                                    
                                    if targets_reached:
                                        print("\nAll category targets reached!")
                                        break
            
            except json.JSONDecodeError as e:
                print(f"JSON parsing error: {e}")
                continue
                
        except Exception as e:
            print(f"Error generating question: {str(e)}")
            traceback.print_exc()
            time.sleep(1)
        
        total_attempts += 1
        if total_attempts % 10 == 0:
            print(f"\nAttempts: {total_attempts}/{max_attempts}")
            print("Current category counts:")
            for cat, count in category_counts.items():
                print(f"- {cat}: {count}/{pool_targets[cat]}")
    
    print(f"\nGenerated {len(question_pool)} questions in {total_attempts} attempts")
    
    # Select diverse questions
    print("\nSelecting diverse questions...")
    selected = select_diverse_questions(question_pool, num_questions, required_categories)
    print(f"\nSelected {len(selected)} diverse questions")
    
    return selected

def select_diverse_category_questions(questions, count):
    """Select diverse questions within a category."""
    if not questions:
        return []
    
    # Create a diversity matrix between questions
    diversity_matrix = []
    for q1 in questions:
        row = []
        for q2 in questions:
            diversity_score = calculate_question_diversity(q1, q2)
            row.append(diversity_score)
        diversity_matrix.append(row)
    
    # Select the most diverse questions
    selected_indices = [0]  # Start with the first question
    while len(selected_indices) < count and len(selected_indices) < len(questions):
        max_min_distance = -1
        best_index = -1
        
        # For each unchosen question
        for i in range(len(questions)):
            if i in selected_indices:
                continue
            
            # Find the minimum distance to already selected questions
            min_distance = float('inf')
            for j in selected_indices:
                distance = diversity_matrix[i][j]
                min_distance = min(min_distance, distance)
            
            # Select the question with the maximum minimum distance
            if min_distance > max_min_distance:
                max_min_distance = min_distance
                best_index = i
        
        if best_index != -1:
            selected_indices.append(best_index)
    
    return [questions[i] for i in selected_indices]

def select_diverse_questions(pool, num_questions, required_categories):
    """Select most diverse questions from pool."""
    # Распределяем вопросы по категориям
    questions_by_category = defaultdict(list)
    for q in pool:
        questions_by_category[q['category']].append(q)
    
    # Проверяем наличие всех требуемых категорий
    missing_categories = set(required_categories) - set(questions_by_category.keys())
    if missing_categories:
        print(f"Warning: Missing questions for categories: {missing_categories}")
    
    # Вычисляем количество вопросов для каждой категории
    target_per_category = num_questions // len(required_categories)
    extra = num_questions % len(required_categories)
    
    selected = []
    used_questions = set()  # Для отслеживания уникальных вопросов
    
    # Сначала выбираем минимальное количество вопросов для каждой категории
    for category in required_categories:
        if category not in questions_by_category:
            continue
            
        category_questions = questions_by_category[category]
        
        # Фильтруем некорректные значения и дубликаты
        filtered_questions = []
        for q in category_questions:
            # Создаем ключ для проверки дубликатов
            question_key = (
                q['category'],
                q['metric'],
                q['timeframe'],
                str(float(q['target_value'])),
                q['question'].lower()  # Добавляем сам вопрос в нижнем регстре
            )
            
            if question_key not in used_questions:
                # Проверяем корректность target_value
                try:
                    value = float(q['target_value'])
                    if category == 'cryptocurrency':
                        # Проверяем диапазон для криптовалют
                        if 'ATOM' in q['question'] and value > 20:  # Для Cosmos
                            continue
                        if 'BTC' in q['question'] and value > 200000:  # Для Bitcoin
                            continue
                        if 'DOT' in q['question'] and value > 20:  # Для Polkadot
                            continue
                    elif category == 'social_events':
                        if not (50 <= value <= 500):
                            continue
                    
                    filtered_questions.append(q)
                    used_questions.add(question_key)
                except (ValueError, TypeError):
                    continue
        
        # Выбираем самые разные вопросы
        target_count = target_per_category + (1 if extra > 0 else 0)
        diverse_questions = select_diverse_category_questions(
            filtered_questions,
            target_count
        )
        
        selected.extend(diverse_questions)
        if extra > 0:
            extra -= 1
    
    # Если не хватает вопросов, добавляем из оставшихся категорий
    while len(selected) < num_questions:
        for category in required_categories:
            if len(selected) >= num_questions:
                break
                
            if category not in questions_by_category:
                continue
                
            remaining = [
                q for q in questions_by_category[category] 
                if q not in selected and 
                (q['category'], q['metric'], q['timeframe'], str(float(q['target_value'])), q['question'].lower()) not in used_questions
            ]
            
            if remaining:
                question = remaining[0]
                selected.append(question)
                used_questions.add((
                    question['category'],
                    question['metric'],
                    question['timeframe'],
                    str(float(question['target_value'])),
                    question['question'].lower()
                ))
    
    print(f"\nSelected {len(selected)} diverse questions")
    print("\nCategory distribution:")
    category_counts = defaultdict(int)
    for q in selected:
        category_counts[q['category']] += 1
    for cat, count in category_counts.items():
        print(f"- {cat}: {count} ({count/len(selected)*100:.1f}%)")
    
    return selected[:num_questions]

def calculate_question_diversity(q1, q2):
    """Calculate diversity score between two questions."""
    score = 0
    
    # Разные метрики
    if q1['metric'] != q2['metric']:
        score += 1
    
    # Разые временные рамки
    try:
        date1 = datetime.strptime(q1['timeframe'], '%Y/%m/%d')
        date2 = datetime.strptime(q2['timeframe'], '%Y/%m/%d')
        if abs((date1 - date2).days) > 30:  # Разница больше месяца
            score += 1
    except ValueError:
        pass
    
    # Разные значения
    try:
        val1 = float(q1['target_value'])
        val2 = float(q2['target_value'])
        if abs(val1 - val2) / max(val1, val2) > 0.2:  # Разница больше 20%
            score += 1
    except (ValueError, TypeError, ZeroDivisionError):
        pass
    
    # Разные сущности
    entities1 = set(re.findall(r'\b[A-Z]{2,}\b', q1['question']))
    entities2 = set(re.findall(r'\b[A-Z]{2,}\b', q2['question']))
    if not entities1.intersection(entities2):
        score += 1
    
    # Разные страны (для social_events)
    if q1['category'] == 'social_events' and q2['category'] == 'social_events':
        country1 = next((c for c in entities1 if len(c) == 3), '')
        country2 = next((c for c in entities2 if len(c) == 3), '')
        if country1 != country2:
            score += 2  # Больший вес для разных стран
    
    return score

def clean_json_content(content):
    """Clean and fix common JSON issues."""
    try:
        # Extract first valid JSON object
        start = content.find('{')
        end = content.rfind('}') + 1
        if start == -1 or end == 0:
            return '[]'
            
        content = content[start:end]
        
        # Basic cleanup
        content = content.replace('\n', ' ')
        content = content.replace('\\"', '"')
        content = content.replace('\\\\', '\\')
        
        # Fix JSON structure markers
        content = re.sub(r'",\s*"', '", "', content)  # Fix spacing between fields
        content = re.sub(r'":\s*"', '": "', content)  # Fix spacing around colons
        
        # Remove unwanted characters
        content = content.replace('$', '')
        content = content.replace('[increase/decrease]', 'increase')
        content = content.replace('YoY', '')
        content = content.replace('%', '')
        content = content.replace('Trillion', '000000000000')
        content = content.replace('Billion', '000000000')
        content = content.replace('Million', '000000')
        
        # Fix numeric values first
        content = re.sub(r'(\d+)/\d+/\d+(?=")', r'\1', content)
        content = re.sub(r'(\d+)k\b', lambda m: str(int(m.group(1)) * 1000), content)
        content = re.sub(r'(\d+)m\b', lambda m: str(int(m.group(1)) * 1000000), content)
        content = re.sub(r'(\d+)b\b', lambda m: str(int(m.group(1)) * 1000000000), content)
        content = re.sub(r'(\d+)t\b', lambda m: str(int(m.group(1)) * 1000000000000), content)
        
        # Fix target values
        if '"target_value":' in content:
            # Remove commas and currency symbols
            content = re.sub(r'"target_value":\s*"[\$,]*(\d+\.?\d*)"', r'"target_value": \1', content)
            
            # Handle ranges
            if '[' in content:
                match = re.search(r'"target_value":\s*\[\s*(\d+\.?\d*)[^\]]*\]', content)
                if match:
                    content = re.sub(r'"target_value":\s*\[[^\]]*\]', f'"target_value": {match.group(1)}', content)
        
        # Fix date formats
        if 'timeframe' in content:
            # Extract date from question if present
            date_match = re.search(r'by (\d{4}/\d{2}/\d{2})', content)
            if date_match:
                extracted_date = date_match.group(1)
                content = re.sub(r'"timeframe":\s*"[^"]*"', f'"timeframe": "{extracted_date}"', content)
            else:
                # Default date handling
                content = content.replace('YYYY/MM/DD', '2025/04/01')
                content = re.sub(r'"timeframe":\s*"[^"]*to[^"]*"', '"timeframe": "2025/04/01"', content)
                content = re.sub(r'"timeframe":\s*"[^"]*by ([^"]+)\s*\d{4}"', r'"timeframe": "2025/04/01"', content)
                content = re.sub(r'"timeframe":\s*"(\d{4})/(\d{2})/(\d{2})"', r'"timeframe": "\1/\2/\3"', content)
                content = re.sub(r'"timeframe":\s*"(\d{4})"', r'"timeframe": "\1/04/01"', content)  # Changed from 12/01
                content = re.sub(r'"timeframe":\s*"(\d{4})/(\d{2})"', r'"timeframe": "\1/\2/01"', content)
                content = re.sub(r'(\d{4})(\d{2})(\d{2})', r'\1/\2/\3', content)
        
        # Fix metrics
        if '"category": "financial_market"' in content:
            content = re.sub(r'"metric":\s*"24h_change"', '"metric": "price_target"', content)
            content = re.sub(r'"metric":\s*"volume_24h"', '"metric": "volume_target"', content)
            content = re.sub(r'"metric":\s*"market_cap_24h"', '"metric": "market_cap_target"', content)
        
        if '"category": "economic_indicator"' in content:
            if 'Treasury' in content:
                content = re.sub(r'"metric":\s*"[^"]*Treasury[^"]*"', '"metric": "treasury_rate"', content)
                content = re.sub(r'Will the [^"]+ Treasury [^"]+ by ([^"]+)', r'Will Treasury rate reach \1', content)
            content = re.sub(r'"metric":\s*"[^"]*Consumer Price Index[^"]*"', '"metric": "cpi"', content)
            content = re.sub(r'"metric":\s*"[^"]*Industrial Production[^"]*"', '"metric": "industrial_production"', content)
            content = re.sub(r'"metric":\s*"[^"]*GDP[^"]*"', '"metric": "gdp"', content)
            content = re.sub(r'"metric":\s*"[^"]*Unemployment[^"]*"', '"metric": "unemployment_rate"', content)
            content = re.sub(r'"metric":\s*"[^"]*Inflation[^"]*"', '"metric": "inflation_rate"', content)
            content = re.sub(r'"metric":\s*"[^"]*yield[^"]*"', '"metric": "treasury_rate"', content)
            content = re.sub(r'"metric":\s*"[^"]*interest[^"]*"', '"metric": "interest_rate"', content)
            content = re.sub(r'"metric":\s*"[^"]*Percent[^"]*"', '"metric": "treasury_rate"', content)
        
        # Fix measurement source
        if '"category": "cryptocurrency"' in content:
            content = re.sub(r'"measurement_source":\s*"[^"]*"', '"measurement_source": "CoinMarketCap"', content)
            if not '"measurement_source"' in content:
                content = content.rstrip('}') + ', "measurement_source": "CoinMarketCap"}'
        elif '"category": "economic_indicator"' in content:
            content = re.sub(r'"measurement_source":\s*"[^"]*"', '"measurement_source": "FRED database"', content)
            if not '"measurement_source"' in content:
                content = content.rstrip('}') + ', "measurement_source": "FRED database"}'
        elif '"category": "social_events"' in content:
            content = re.sub(r'"measurement_source":\s*"[^"]*"', '"measurement_source": "ACLED database"', content)
            if not '"measurement_source"' in content:
                content = content.rstrip('}') + ', "measurement_source": "ACLED database"}'
        elif '"category": "financial_market"' in content:
            content = re.sub(r'"measurement_source":\s*"[^"]*"', '"measurement_source": "EOD Historical Data"', content)
            if not '"measurement_source"' in content:
                content = content.rstrip('}') + ', "measurement_source": "EOD Historical Data"}'
        
        # Fix missing quotes around values
        content = re.sub(r':\s*([^",\{\}\[\]\s][^",\{\}\[\]]*[^",\{\}\[\]\s])\s*([,}])', r': "\1"\2', content)
        
        # Fix truncated content
        if not content.endswith('}'):
            content += '}'
        if content.count('{') > content.count('}'):
            content += '}'
            
        # Final cleanup
        content = re.sub(r',\s*}', '}', content)
        content = re.sub(r'\s+', ' ', content)
        
        # Wrap in array if it's a single object
        if content.startswith('{'):
            content = '[' + content + ']'
        
        # Verify JSON is valid
        try:
            json.loads(content)
        except json.JSONDecodeError:
            # If invalid, try aggressive cleanup
            content = re.sub(r'([^"]),\s*([^"\d{[])', r'\1, "\2', content)
            content = re.sub(r'([^"}]),\s*}', r'\1}', content)
            content = re.sub(r'",\s*"', '", "', content)
            content = re.sub(r'":\s*"', '": "', content)
        
        return content
    except Exception as e:
        print(f"Error cleaning JSON: {str(e)}")
        print(f"Original content: {content}")
        return '[]'

def repair_json(content):
    """Attempt to repair broken JSON."""
    try:
        # Basic cleanup
        content = content.strip()
        if not content:
            return None
        
        # Extract all JSON objects
        objects = []
        current = ""
        brace_count = 0
        
        for char in content:
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
            
            current += char
            
            if brace_count == 0 and current.strip():
                if current.startswith('{') and current.endswith('}'):
                    # Fix measurement source if truncated
                    if '"measurement_source": "' in current and not current.endswith('"}'):
                        if 'financial_market' in current:
                            current = current.replace('"measurement_source": "', '"measurement_source": "EOD Historical Data"}')
                        elif 'cryptocurrency' in current:
                            current = current.replace('"measurement_source": "', '"measurement_source": "CoinMarketCap"}')
                        elif 'social_events' in current:
                            current = current.replace('"measurement_source": "', '"measurement_source": "ACLED database"}')
                        elif 'economic_indicator' in current:
                            current = current.replace('"measurement_source": "', '"measurement_source": "FRED database"}')
                    
                    try:
                        # Verify it's valid JSON
                        json.loads(current)
                        objects.append(current)
                    except:
                        pass
                current = ""
        
        if not objects:
            return None
        
        # Combine into array
        content = '[' + ','.join(objects) + ']'
        
        try:
            return json.loads(content)
        except:
            # If still failing, try more aggressive cleanup
            content = re.sub(r'[^\[\]{}",:.\d\w\s-]', '', content)
            return json.loads(content)
    except Exception as e:
        print(f"Error repairing JSON: {str(e)}")
        return None

def process_ollama_response(response, crypto_data=None, countries=None):
    """Process response from Ollama."""
    try:
        content = clean_json_content(response['message']['content'])
        print("Cleaned content:", content[:200])
        
        try:
            questions = json.loads(content)
            if not isinstance(questions, list):
                questions = [questions]
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}")
            return []
            
        validated_questions = []
        used_keys = set()
        
        for question in questions:
            if validate_single_question(question, crypto_data=crypto_data, countries=countries):
                key = create_question_key(question)
                if key not in used_keys:
                    validated_questions.append(question)
                    used_keys.add(key)
                    
        return validated_questions
        
    except Exception as e:
        print(f"Error processing Ollama response: {e}")
        traceback.print_exc()
        return []

async def generate_questions_batch_ollama_async(news_headlines, fred_data, acled_data, crypto_data, num_questions, required_categories=None, market_data=None):
    """Асинхронная генерация вопросов через Ollama."""
    fred_context = create_fred_context(fred_data)
    acled_context = create_acled_context(acled_data)
    crypto_context = create_crypto_context(crypto_data) if crypto_data else ""
    market_context = create_market_context(market_data) if market_data else ""
    
    # Добавляем информацию о требуемых категориях в промпт
    if required_categories:
        categories_str = ", ".join(required_categories)
        extra_prompt = f"\nIMPORTANT: Generate questions ONLY for these categories: {categories_str}"
    else:
        extra_prompt = ""
    
    prompt = create_prompt(num_questions, fred_context, acled_context, crypto_context, news_headlines, market_context) + extra_prompt
    
    max_retries = 3
    retry_delay = 5
    timeout = aiohttp.ClientTimeout(total=60)
    
    for attempt in range(max_retries):
        try:
            response = ollama.chat(
                model='llama3.2:3b',
                messages=[
                    {
                        'role': 'system',
                        'content': get_system_prompt()
                    },
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ]
            )
            
            questions = process_ollama_response(response, crypto_data=crypto_data)
            if questions:
                return questions
            
            await asyncio.sleep(retry_delay)
                    
        except asyncio.TimeoutError:
            print(f"Request timed out (attempt {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
        except Exception as e:
            print(f"Error in async Ollama generation: {str(e)}")
            print(f"Full error details: {type(e).__name__}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
    
    return []

async def check_ollama_server():
    """роверка доступности Ollama серера."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('http://localhost:11434/api/version') as response:
                if response.status == 200:
                    return True
                return False
    except:
        return False

async def generate_questions_ollama_parallel(news_headlines, fred_data, acled_data, crypto_data, num_questions, batch_size=5, required_categories=None, market_data=None):
    """Параллельная геерация вопросов через Ollama."""
    if not await check_ollama_server():
        print("Error: Ollama server is not available")
        return []
    
    if num_questions > 10:
        batch_size = min(3, batch_size)
    
    tasks = []
    for i in range(0, num_questions, batch_size):
        current_batch_size = min(batch_size, num_questions - i)
        task = asyncio.create_task(
            generate_questions_batch_ollama_async(
                news_headlines,
                fred_data,
                acled_data,
                crypto_data,
                current_batch_size,
                required_categories=required_categories,
                market_data=market_data
            )
        )
        tasks.append(task)
        await asyncio.sleep(0.5)
    
    try:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        all_questions = []
        for result in results:
            if isinstance(result, Exception):
                print(f"Task failed with error: {result}")
                continue
            if result:
                all_questions.extend(result)
        return all_questions
    except Exception as e:
        print(f"Error in parallel generation: {str(e)}")
        return []

def create_market_context(market_data):
    """Create context string from market data."""
    if not market_data:
        return ""
        
    context = "Current Market Data:\n"
    for symbol, data in market_data.items():
        context += (
            f"- {data['name']} ({symbol}):\n"
            f"  Price: ${data['price']:.2f}\n"
            f"  Volume: {data['volume']:,.0f}\n"
            f"  Market Cap: ${data['market_cap']:,.2f}\n"
            f"  24h Change: {data['change_percent']:.2f}%\n"
        )
    return context

def validate_question_for_pool(question, used_questions, crypto_data):
    """Validate question for inclusion in the pool."""
    try:
        # Базовая валидация
        if not all(key in question for key in ['question', 'timeframe', 'category', 'metric', 'target_value']):
            print(f"Missing required fields in question: {question}")
            return False
        
        # Проверяем уникальность вопроса
        if question['question'] in used_questions:
            print("Duplicate question")
            return False
        
        # Проверяем формат даты
        try:
            timeframe = datetime.strptime(question['timeframe'], '%Y/%m/%d')
            if not (datetime(2024, 12, 1) <= timeframe <= datetime(2025, 6, 30)):
                print(f"Invalid timeframe: {question['timeframe']}")
                return False
        except ValueError:
            print(f"Invalid date format: {question['timeframe']}")
            return False
        
        # Проверяем значения в зависимости от категории
        category = question['category']
        metric = question['metric'].lower()
        
        # Преобразуем target_value в число
        try:
            if isinstance(question['target_value'], list):
                value = float(question['target_value'][0])
            else:
                value = float(question['target_value'])
        except (ValueError, TypeError, IndexError):
            print(f"Invalid target value: {question['target_value']}")
            return False
        
        if category == 'economic_indicator':
            valid_ranges = {
                'gdp': (20000, 50000),
                'unemployment_rate': (2, 15),
                'inflation_rate': (-2, 15),
                'cpi': (200, 400),
                'treasury_rate': (-5, 10),
                'industrial_production': (80, 120)
            }
            
            # Находим подходящий диапазон по ключевым словам
            for key, (min_val, max_val) in valid_ranges.items():
                if key in metric:
                    if min_val <= value <= max_val:
                        return True
                    print(f"Value {value} outside range [{min_val}, {max_val}] for {key}")
                    return False
            return True  # Если метрика не найдена, пропускаем
        
        elif category == 'cryptocurrency':
            for symbol, data in crypto_data.items():
                if symbol in question['question'] or data['name'] in question['question']:
                    current_price = float(data['price'])
                    min_price = current_price * 0.5
                    max_price = current_price * 2.0
                    if min_price <= value <= max_price:
                        return True
                    print(f"Crypto price {value} outside range ({min_price:.2f} - {max_price:.2f}) for {symbol}")
                    return False
            print("Unknown cryptocurrency in question")
            return False
        
        elif category == 'social_events':
            if not (50 <= value <= 500):
                print(f"Invalid protest count: {value}")
                return False
            return True
        
        elif category == 'financial_market':
            if 'price' in metric:
                if value <= 0:
                    print(f"Invalid price value: {value}")
                    return False
            elif 'volume' in metric:
                if value < 1000:
                    print(f"Invalid volume value: {value}")
                    return False
            elif 'market_cap' in metric:
                if value < 1000000:
                    print(f"Invalid market cap value: {value}")
                    return False
            return True
        
        return True
        
    except Exception as e:
        print(f"Error validating question: {e}")
        traceback.print_exc()
        return False

class timeout:
    def __init__(self, seconds=1, error_message='Timeout'):
        self.seconds = seconds
        self.error_message = error_message

    def handle_timeout(self, signum, frame):
        raise TimeoutError(self.error_message)

    def __enter__(self):
        signal.signal(signal.SIGALRM, self.handle_timeout)
        signal.alarm(self.seconds)

    def __exit__(self, type, value, traceback):
        signal.alarm(0)

def normalize_target_value(value, category, metric, crypto_data=None):
    """Normalize target value based on category and metric."""
    try:
        if isinstance(value, str):
            value = float(value.replace('$', '').replace(',', ''))
        
        if category == 'cryptocurrency' and crypto_data:
            # Ограничиваем значения для криптовалют
            for symbol, data in crypto_data.items():
                current_price = float(data['price'])
                min_price = current_price * 0.5
                max_price = current_price * 2.0
                if min_price <= value <= max_price:
                    return value
            return None
            
        elif category == 'social_events':
            # Ограничиваем значения для протестов
            if 50 <= value <= 500:
                return value
            return None
            
        elif category == 'economic_indicator':
            # Ограничиваем значения для экономических индикаторов
            ranges = {
                'gdp': (20000, 50000),
                'unemployment': (2, 15),
                'inflation': (-2, 15),
                'interest': (-5, 10),
                'treasury': (-5, 10)
            }
            
            for key, (min_val, max_val) in ranges.items():
                if key in metric.lower():
                    if min_val <= value <= max_val:
                        return value
                    return None
                    
        return value
        
    except (ValueError, TypeError):
        return None

def create_question_key(question):
    """Create unique key for question."""
    return (
        question['category'],
        question['metric'],
        question['timeframe'],
        str(float(question['target_value'])),
        re.sub(r'\s+', ' ', question['question'].lower().strip())
    )

__all__ = [
    'generate_questions_batch_ollama',
    'generate_questions_ollama_parallel',
    'generate_questions_batch_ollama_async',
    'create_fred_context',
    'create_acled_context',
    'create_prompt',
    'get_system_prompt',
    'process_ollama_response'
] 
