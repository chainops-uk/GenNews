from datetime import datetime, timedelta
from ..utils.cache import load_cached_data, save_to_cache
import os

def get_financial_news(newsapi, cache_dir):
    """Fetches the latest financial news headlines."""
    print("Starting news fetch process...")
    cache_path = os.path.join(cache_dir, 'news_cache.json')
    cache_max_age = 1800  # 30 minutes

    # Check cache first
    print(f"Checking cache at: {cache_path}")
    cached_data = load_cached_data(cache_path)
    if cached_data:
        cache_time = datetime.fromtimestamp(os.path.getmtime(cache_path))
        if datetime.now() - cache_time < timedelta(seconds=cache_max_age):
            print(f"Using cached news data (age: {datetime.now() - cache_time})")
            return cached_data

    print("Cache not found or expired, fetching fresh data...")
    try:
        print("Making NewsAPI request...")
        top_headlines = newsapi.get_top_headlines(
            category='business',
            language='en',
            country='us',
            page_size=50
        )
        print("NewsAPI request completed")
        
        articles = top_headlines.get('articles', [])
        print(f"Retrieved {len(articles)} articles")
        
        if not articles:
            print("Warning: No articles available from NewsAPI")
            raise APIError("No articles available.")
        
        headlines = [article['title'] for article in articles]
        print(f"Extracted {len(headlines)} headlines")
        
        # Cache the data
        print("Saving to cache...")
        save_to_cache(headlines, cache_path)
        print("Cache saved successfully")
        
        return headlines
    except Exception as e:
        print(f"Error in get_financial_news: {e}")
        return [] 
