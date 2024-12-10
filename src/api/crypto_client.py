import requests
from datetime import datetime
import json

class CryptoClient:
    def __init__(self, api_key, cache_dir=None):
        self.api_key = api_key
        self.cache_dir = cache_dir
        self.base_url = 'https://pro-api.coinmarketcap.com/v1'
        self.headers = {
            'X-CMC_PRO_API_KEY': api_key,
            'Accept': 'application/json'
        }

    def get_crypto_data(self, symbols=None):
        """Get cryptocurrency data from CoinMarketCap."""
        url = f"{self.base_url}/cryptocurrency/quotes/latest"
        
        params = {
            'symbol': ','.join(symbols) if symbols else 'BTC,ETH,BNB,TAO',
            'convert': 'USD'
        }
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            data = response.json()
            
            if 'data' in data:
                return self._process_crypto_data(data['data'])
            else:
                print(f"Error getting crypto data: {data.get('status', {}).get('error_message')}")
                return {}
                
        except Exception as e:
            print(f"Error fetching crypto data: {e}")
            return {}
    
    def _process_crypto_data(self, data):
        """Process cryptocurrency data."""
        processed_data = {}
        for symbol, crypto in data.items():
            quote = crypto['quote']['USD']
            processed_data[symbol] = {
                'name': crypto['name'],
                'symbol': crypto['symbol'],
                'price': quote['price'],
                'market_cap': quote['market_cap'],
                'volume_24h': quote['volume_24h'],
                'percent_change_24h': quote['percent_change_24h'],
                'last_updated': quote['last_updated']
            }
        return processed_data

def create_crypto_context(crypto_data):
    """Create context string from crypto data."""
    context = "Current Cryptocurrency Market Data:\n"
    for symbol, data in crypto_data.items():
        context += (
            f"- {data['name']} ({symbol}):\n"
            f"  Price: ${data['price']:.2f}\n"
            f"  Market Cap: ${data['market_cap']:.2f}\n"
            f"  24h Volume: ${data['volume_24h']:.2f}\n"
            f"  24h Change: {data['percent_change_24h']:.2f}%\n"
        )
    return context 
