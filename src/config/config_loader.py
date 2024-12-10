import json
import os
from dotenv import load_dotenv

def load_config(config_path=None):
    """Load configuration from .env file."""
    if config_path:
        load_dotenv(config_path)
    else:
        load_dotenv()

    config = {
        'openai_key': os.getenv('OPENAI_API_KEY'),
        'newsapi_key': os.getenv('NEWS_API_KEY'),
        'fred_key': os.getenv('FRED_API_KEY'),
        'acled_key': os.getenv('ACLED_API_KEY'),
        'acled_email': os.getenv('ACLED_EMAIL'),
        'coinmarketcap_key': os.getenv('COINMARKETCAP_API_KEY'),
        'eodhd_key': os.getenv('EODHD_API_KEY')
    }
    
    return config

def validate_api_keys(config):
    """Validate that all required API keys are present."""
    required_keys = {
        'openai_key': 'OPENAI_API_KEY',
        'newsapi_key': 'NEWS_API_KEY',
        'fred_key': 'FRED_API_KEY',
        'acled_key': 'ACLED_API_KEY',
        'acled_email': 'ACLED_EMAIL',
        'coinmarketcap_key': 'COINMARKETCAP_API_KEY',
        'eodhd_key': 'EODHD_API_KEY'
    }
    
    missing_keys = []
    for key, env_name in required_keys.items():
        if not config.get(key):
            missing_keys.append(env_name)
    
    if missing_keys:
        raise ValueError(f"Missing required API keys in .env file: {', '.join(missing_keys)}")
