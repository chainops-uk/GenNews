import requests
from datetime import datetime
import json

class EODHDClient:
    def __init__(self, api_key, cache_dir=None):
        self.api_key = api_key
        self.cache_dir = cache_dir
        self.base_url = 'https://eodhd.com/api'

    def _safe_float(self, value, default=0.0):
        """Safely convert value to float, handling 'NA' and other invalid values."""
        if value is None or value == 'NA' or value == '':
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    def _safe_int(self, value, default=0):
        """Safely convert value to int, handling 'NA' and other invalid values."""
        if value is None or value == 'NA' or value == '':
            return default
        try:
            return int(float(value))  # Convert through float to handle string numbers
        except (ValueError, TypeError):
            return default

    def get_stock_data(self, symbols):
        """Get real-time stock data from EODHD."""
        if not symbols:
            return {}

        url = f"{self.base_url}/real-time/stock"
        params = {
            'api_token': self.api_key,
            'fmt': 'json',
            's': ','.join(symbols)
        }

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()  # Raise exception for bad status codes
            data = response.json()
            
            if isinstance(data, dict) and 'error' in data:
                print(f"Error getting stock data: {data['error']}")
                return {}
            
            processed_data = self._process_stock_data(data)
            if not processed_data:
                print("Warning: No valid stock data received")
            else:
                print(f"Successfully retrieved data for {len(processed_data)} stocks")
            
            return processed_data
            
        except requests.exceptions.RequestException as e:
            print(f"Request error fetching stock data: {str(e)}")
            return {}
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON response: {str(e)}")
            return {}
        except Exception as e:
            print(f"Unexpected error fetching stock data: {str(e)}")
            return {}
    
    def _process_stock_data(self, data):
        """Process stock market data."""
        processed_data = {}
        try:
            # Check if data is a list (API sometimes returns list instead of dict)
            if isinstance(data, list):
                for stock in data:
                    if 'code' in stock:  # Use stock code as symbol
                        symbol = stock['code']
                        processed_data[symbol] = {
                            'name': stock.get('name', ''),
                            'price': self._safe_float(stock.get('close')),
                            'volume': self._safe_int(stock.get('volume')),
                            'market_cap': self._safe_float(stock.get('market_cap')),
                            'change_percent': self._safe_float(stock.get('change_p')),
                            'last_updated': stock.get('timestamp', '')
                        }
            else:  # Process as dictionary
                for symbol, stock_data in data.items():
                    processed_data[symbol] = {
                        'name': stock_data.get('name', ''),
                        'price': self._safe_float(stock_data.get('close')),
                        'volume': self._safe_int(stock_data.get('volume')),
                        'market_cap': self._safe_float(stock_data.get('market_cap')),
                        'change_percent': self._safe_float(stock_data.get('change_p')),
                        'last_updated': stock_data.get('timestamp', '')
                    }
            
            # Filter out entries with zero or invalid prices
            processed_data = {
                symbol: data for symbol, data in processed_data.items()
                if data['price'] > 0
            }
            
            return processed_data
        except Exception as e:
            print(f"Error processing stock data: {str(e)}")
            return {}

def create_market_context(market_data):
    """Create context string from market data."""
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
