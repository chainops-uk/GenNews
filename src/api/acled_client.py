import requests
from datetime import datetime, timedelta
import json
import os
from ..utils.cache import load_cached_data, save_to_cache

class ACLEDClient:
    """Client for interacting with ACLED API."""
    
    BASE_URL = "https://api.acleddata.com/acled/read"
    
    def __init__(self, api_key, email, cache_dir=None):
        self.api_key = api_key
        self.email = email
        self.cache_dir = cache_dir
        
    def get_conflicts(self, countries=None, start_date=None, end_date=None, event_types=None):
        """
        Fetch conflict data from ACLED API.
        
        Args:
            countries (list): List of ISO country codes
            start_date (str): Start date in YYYY-MM-DD format
            end_date (str): End date in YYYY-MM-DD format
            event_types (list): List of event types to filter
            
        Returns:
            dict: Processed conflict data with structure:
            {
                'summary': {
                    'total_events': int,
                    'total_fatalities': int,
                    'event_types': dict,
                    'actor_types': dict,
                    'countries': list
                },
                'events': list,
                'time_series': dict,
                'countries': list
            }
        """
        # Check cache first
        if self.cache_dir:
            cache_path = os.path.join(self.cache_dir, 'acled_cache.json')
            cache_data = load_cached_data(cache_path)
            if cache_data:
                cache_time = datetime.fromtimestamp(os.path.getmtime(cache_path))
                if datetime.now() - cache_time < timedelta(hours=24):
                    print("Using cached ACLED data")
                    return cache_data
        
        # Prepare API request
        params = {
            'key': self.api_key,
            'email': self.email,
            'terms': 'accept'
        }
        
        # Add country filter
        if countries:
            params['iso'] = '|'.join(countries)
            params['iso_where'] = '='
        
        # Add date filter
        if start_date and end_date:
            params['event_date'] = f"{start_date}|{end_date}"
            params['event_date_where'] = 'BETWEEN'
            
        # Add event type filter
        if event_types:
            params['event_type'] = '|'.join(event_types)
            params['event_type_where'] = '='
        
        print(f"Making ACLED API request with params: {params}")
        
        try:
            response = requests.get(self.BASE_URL, params=params)
            print(f"Response status code: {response.status_code}")
            
            if response.status_code != 200:
                print(f"API Error response: {response.text}")
                return self._create_empty_data(countries)
            
            data = response.json()
            if 'error' in data:
                print(f"API Error: {data['error']}")
                return self._create_empty_data(countries)
            
            events = data.get('data', [])
            if not events:
                print("No events found for the specified criteria")
                return self._create_empty_data(countries)
            
            # Process events
            processed_data = {
                'summary': {
                    'total_events': len(events),
                    'total_fatalities': sum(self._safe_int(e.get('fatalities', 0)) for e in events),
                    'event_types': {},
                    'actor_types': {},
                    'countries': countries
                },
                'events': events,
                'time_series': self.get_time_series(events),
                'countries': countries
            }
            
            # Count event types and actors
            for event in events:
                event_type = event.get('event_type')
                if event_type:
                    processed_data['summary']['event_types'][event_type] = \
                        processed_data['summary']['event_types'].get(event_type, 0) + 1
                
                actor1_type = event.get('actor1', 'Unknown')
                processed_data['summary']['actor_types'][actor1_type] = \
                    processed_data['summary']['actor_types'].get(actor1_type, 0) + 1
            
            # Save to cache
            if self.cache_dir:
                save_to_cache(processed_data, cache_path)
            
            return processed_data
            
        except requests.exceptions.RequestException as e:
            print(f"Error making API request: {e}")
            return self._create_empty_data(countries)
        except Exception as e:
            print(f"Unexpected error: {e}")
            return self._create_empty_data(countries)
    
    def _create_empty_data(self, countries):
        """Create empty data structure with specified countries."""
        return {
            'summary': {
                'total_events': 0,
                'total_fatalities': 0,
                'event_types': {},
                'actor_types': {},
                'countries': countries
            },
            'events': [],
            'time_series': {},
            'countries': countries
        }
    
    def get_time_series(self, events, freq='M'):
        """Generate time series data from events."""
        time_series = {}
        
        for event in events:
            try:
                date = datetime.strptime(event['event_date'], '%Y-%m-%d')
                
                if freq == 'M':
                    key = date.strftime('%Y-%m')
                elif freq == 'W':
                    key = date.strftime('%Y-%W')
                else:
                    key = date.strftime('%Y-%m-%d')
                    
                if key not in time_series:
                    time_series[key] = {
                        'events': 0,
                        'fatalities': 0,
                        'event_types': {}
                    }
                    
                time_series[key]['events'] += 1
                time_series[key]['fatalities'] += self._safe_int(event.get('fatalities', 0))
                
                event_type = event.get('event_type')
                if event_type:
                    time_series[key]['event_types'][event_type] = \
                        time_series[key]['event_types'].get(event_type, 0) + 1
                
            except Exception as e:
                print(f"Error processing event for time series: {e}")
                continue
        
        return time_series
    
    @staticmethod
    def _safe_int(value):
        """Safely convert value to integer."""
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0
