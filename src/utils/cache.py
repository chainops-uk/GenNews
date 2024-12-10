import os
import json

def setup_cache_dir(cache_dir):
    """Create cache directory if it doesn't exist."""
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
    return cache_dir

def load_cached_data(cache_path):
    """Load data from cache if available."""
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading cached data: {e}")
    return None

def save_to_cache(data, cache_path):
    """Save data to cache."""
    try:
        with open(cache_path, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        print(f"Error saving to cache: {e}")

def save_questions_cache(questions, cache_dir):
    """Save generated questions to cache."""
    cache_path = os.path.join(cache_dir, 'questions_cache.json')
    try:
        with open(cache_path, 'w') as f:
            json.dump(questions, f)
    except Exception as e:
        print(f"Error saving questions to cache: {e}")

def load_questions_cache(cache_dir):
    """Load previously generated questions from cache."""
    cache_path = os.path.join(cache_dir, 'questions_cache.json')
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading questions cache: {e}")
    return [] 
