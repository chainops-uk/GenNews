from datetime import datetime, timedelta
import fredapi
from tqdm import tqdm
import os
import json
from ..utils.cache import load_cached_data, save_to_cache

def get_fred_data(fred, cache_dir):
    """Fetches relevant economic indicators from FRED."""
    cache_path = os.path.join(cache_dir, 'fred_cache.json')
    cache_max_age = 3600  # 1 hour

    # Check cache first
    cached_data = load_cached_data(cache_path)
    if cached_data:
        cache_time = datetime.fromtimestamp(os.path.getmtime(cache_path))
        if datetime.now() - cache_time < timedelta(seconds=cache_max_age):
            print("Using cached FRED data")
            return cached_data

    try:
        indicators = {
            'GDP': 'GDP',                    # Gross Domestic Product
            'UNRATE': 'UNRATE',              # Unemployment Rate
            'CPIAUCSL': 'CPIAUCSL',          # Consumer Price Index
            'FEDFUNDS': 'FEDFUNDS',          # Federal Funds Rate
            'T10Y2Y': 'T10Y2Y',              # 10-Year Treasury Constant Maturity Minus 2-Year
            'INDPRO': 'INDPRO',              # Industrial Production Index
            'M2': 'M2',                      # M2 Money Stock
            'HOUST': 'HOUST',                # Housing Starts
            'RSXFS': 'RSXFS',                # Retail Sales
            'PAYEMS': 'PAYEMS'               # Total Nonfarm Payrolls
        }
        
        fred_data = {}
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        
        for name, series_id in tqdm(indicators.items(), desc="Fetching FRED indicators"):
            try:
                series = fred.get_series(series_id, start_date, end_date)
                if not series.empty:
                    latest_value = series.iloc[-1]
                    prev_value = series.iloc[-2] if len(series) > 1 else None
                    yoy_change = ((latest_value / series.iloc[-12]) - 1) * 100 if len(series) >= 12 else None
                    
                    fred_data[name] = {
                        'latest_value': latest_value,
                        'previous_value': prev_value,
                        'yoy_change': yoy_change,
                        'description': fred.get_series_info(series_id).title,
                        'units': fred.get_series_info(series_id).units,
                        'frequency': fred.get_series_info(series_id).frequency,
                        'last_updated': series.index[-1].strftime('%Y-%m-%d')
                    }
            except Exception as e:
                print(f"Error fetching {name}: {e}")
                continue

        # Cache the data
        save_to_cache(fred_data, cache_path)
        return fred_data
    except Exception as e:
        print(f"Error fetching FRED data: {e}")
        return {} 
