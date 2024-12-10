import argparse
import traceback
from openai import OpenAI
from newsapi import NewsApiClient
import fredapi
from datetime import datetime, timedelta

from src import (
    load_config,
    validate_api_keys,
    setup_cache_dir,
    get_fred_data,
    get_financial_news,
    generate_questions_pool,
    save_questions
)
from src.api.acled_client import ACLEDClient
from src.api.crypto_client import CryptoClient, create_crypto_context
from src.api.eodhd_client import EODHDClient, create_market_context

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Generate financial and socio-political questions based on news and data.')
    parser.add_argument('--questions', type=int, default=30,
                       help='Number of questions to generate (default: 30)')
    parser.add_argument('--batch-size', type=int, default=30,
                       help='Number of questions per API call (default: 30)')
    parser.add_argument('--config', type=str,
                       help='Path to configuration file (optional)')
    parser.add_argument('--cache-dir', type=str, default='cache',
                       help='Directory for cached data (default: cache)')
    parser.add_argument('--model', type=str, 
                       choices=['gpt4', 'gpt3.5', 'gpt4-turbo', 'llama2'], 
                       default='gpt4',
                       help='Model to use for generation (default: gpt4)')
    parser.add_argument('--countries', nargs='+', default=['USA', 'GBR', 'FRA'],
                       help='List of ISO 3166-1 alpha-3 country codes for ACLED data (e.g., USA, GBR, FRA)')
    parser.add_argument('--event-types', nargs='+', 
                       default=['Protests', 'Violence against civilians'],
                       choices=['Battles', 'Explosions/Remote violence', 
                               'Violence against civilians', 'Protests', 
                               'Riots', 'Strategic developments'],
                       help='List of event types for ACLED data')
    parser.add_argument('--lookback-days', type=int, default=90,
                       help='Number of days to look back for ACLED data (default: 90)')
    parser.add_argument('--parallel', action='store_true',
                       help='Use parallel generation for GPT-4 (default: False)')
    parser.add_argument('--crypto-symbols', type=str, default='BTC,ETH,BNB,TAO',
                       help='Comma-separated list of cryptocurrency symbols (default: BTC,ETH,BNB,TAO)')
    parser.add_argument('--include-crypto', action='store_true',
                       help='Include cryptocurrency questions in generation')
    parser.add_argument('--include-stocks', action='store_true',
                       help='Include stock market questions in generation')
    parser.add_argument('--stock-symbols', type=str, default='AAPL,MSFT,GOOGL',
                       help='Comma-separated list of stock symbols (default: AAPL,MSFT,GOOGL)')
    return parser.parse_args()

def main():
    try:
        print("Starting program...")
        args = parse_arguments()
        
        config = load_config(args.config)
        validate_api_keys(config)
        
        cache_dir = setup_cache_dir(args.cache_dir)
        
        # Initialize clients
        client = None
        if args.model in ['gpt4', 'gpt3.5', 'gpt4-turbo']:
            client = OpenAI(api_key=config['openai_key'])
            print(f"Using OpenAI model: {args.model}")
        
        newsapi = NewsApiClient(api_key=config['newsapi_key'])
        fred = fredapi.Fred(api_key=config['fred_key'])
        
        # Initialize ACLED client
        acled = ACLEDClient(
            api_key=config['acled_key'],
            email=config['acled_email'],
            cache_dir=cache_dir
        )
        
        # Initialize Crypto client if needed
        crypto_data = {}
        crypto_context = ""
        if args.include_crypto:
            crypto_client = CryptoClient(api_key=config['coinmarketcap_key'], cache_dir=cache_dir)
            symbols = [s.strip() for s in args.crypto_symbols.split(',')]
            crypto_data = crypto_client.get_crypto_data(symbols)
            if crypto_data:
                crypto_context = create_crypto_context(crypto_data)
                print("\nCrypto Data:")
                for symbol, data in crypto_data.items():
                    print(f"- {data['name']} ({symbol}): ${data['price']:.2f}")
        
        # Initialize EODHD client
        eodhd_client = EODHDClient(config['eodhd_key'], cache_dir=cache_dir)
        
        # Get stock data if --include-stocks specified
        market_data = None
        if args.include_stocks:
            stock_symbols = args.stock_symbols.split(',') if args.stock_symbols else []
            market_data = eodhd_client.get_stock_data(stock_symbols)
            print("\nMarket Data:")
            for symbol, data in market_data.items():
                print(f"- {data['name']} ({symbol}): ${data['price']:.2f}")
        
        # Fetch all data
        print("\nFetching data...")
        news_headlines = get_financial_news(newsapi, cache_dir)
        fred_data = get_fred_data(fred, cache_dir)
        
        # Calculate ACLED date range - use current date minus one year
        now = datetime.now()
        end_date = now - timedelta(days=1)  # Yesterday
        start_date = end_date - timedelta(days=args.lookback_days)
        
        print(f"\nFetching ACLED data for {args.countries} from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}...")
        
        # Get ACLED data
        acled_data = acled.get_conflicts(
            countries=args.countries,
            start_date=start_date,
            end_date=end_date,
            event_types=args.event_types
        )
        
        # Process ACLED data
        if not acled_data:
            acled_data = acled._create_empty_data(args.countries)
        
        # Print data summaries
        print("\nData Summary:")
        print(f"News headlines: {len(news_headlines)}")
        print(f"FRED indicators: {len(fred_data)}")
        print(f"ACLED events: {acled_data['summary']['total_events']}")
        
        if acled_data['summary']['event_types']:
            print("\nACLED Event Types:")
            for event_type, count in acled_data['summary']['event_types'].items():
                print(f"- {event_type}: {count}")
        
        # Generate questions
        print(f"\nGenerating {args.questions} questions using {args.model}...")
        questions = generate_questions_pool(
            news_headlines, 
            fred_data,
            acled_data,
            crypto_data,
            num_questions=args.questions,
            pool_size=200,
            required_categories=['economic_indicator', 'social_events', 'cryptocurrency', 'financial_market'],
            market_data=market_data
        )
        
        if questions:
            # Analyze question distribution
            categories = {}
            for q in questions:
                cat = q.get('category', 'unknown')
                categories[cat] = categories.get(cat, 0) + 1
            
            print("\nQuestion Distribution:")
            for cat, count in categories.items():
                print(f"- {cat}: {count} ({count/len(questions)*100:.1f}%)")
            
            save_questions(questions)
        else:
            print("No questions were generated.")
            
    except Exception as e:
        print(f"Error in main execution: {e}")
        print("Full traceback:")
        print(traceback.format_exc())

if __name__ == "__main__":
    print("Script started")
    main()
    print("Script finished") 
