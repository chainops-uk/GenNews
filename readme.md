# GenNews - AI-Powered Question Generator

GenNews is a Python application that generates predictive questions about financial markets, economic indicators, social events, and cryptocurrencies using AI models and real-world data.

## Features

- Multi-category question generation:
  - Financial market predictions (stocks, indices)
  - Economic indicator forecasts
  - Social event predictions (protests, conflicts)
  - Cryptocurrency price predictions

- Data Sources:
  - FRED (Federal Reserve Economic Data)
  - ACLED (Armed Conflict Location & Event Data)
  - CoinMarketCap (Cryptocurrency data)
  - EOD Historical Data (Stock market data)
  - NewsAPI (Current news headlines)

- AI Models Support:
  - GPT-4
  - GPT-3.5
  - GPT-4 Turbo
  - Llama2

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/genews.git
cd genews
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a configuration file `config.json`:
```json
{
    "openai_key": "your-openai-key",
    "fred_key": "your-fred-key",
    "acled_key": "your-acled-key",
    "acled_email": "your-email",
    "newsapi_key": "your-newsapi-key",
    "coinmarketcap_key": "your-coinmarketcap-key",
    "eodhd_key": "your-eodhd-key"
}
```

## Usage

Basic usage:
```bash
python main.py --questions 50 --model llama2
```

Full options:
```bash
python main.py \
    --questions 50 \
    --batch-size 5 \
    --crypto-symbols "ATOM,NEO,TAO,XLM" \
    --include-crypto \
    --include-stocks \
    --stock-symbols "AAPL,MSFT,GOOGL,TSLA" \
    --countries USA GBR FRA \
    --event-types "Protests" "Riots" "Violence against civilians" \
    --lookback-days 90 \
    --model llama2
```

### Command Line Arguments

- `--questions`: Number of questions to generate (default: 30)
- `--batch-size`: Questions per API call (default: 30)
- `--model`: AI model to use (choices: gpt4, gpt3.5, gpt4-turbo, llama2)
- `--countries`: List of ISO 3166-1 alpha-3 country codes for ACLED data
- `--event-types`: Types of events to track (choices: Battles, Explosions/Remote violence, Violence against civilians, Protests, Riots, Strategic developments)
- `--lookback-days`: Days of historical data to consider (default: 90)
- `--include-crypto`: Include cryptocurrency questions
- `--crypto-symbols`: List of cryptocurrency symbols
- `--include-stocks`: Include stock market questions
- `--stock-symbols`: List of stock symbols
- `--parallel`: Use parallel generation for GPT-4
- `--cache-dir`: Directory for cached data (default: cache)

## Data Sources Configuration

### ACLED API
- Register at [ACLED](https://acleddata.com/register)
- Use your API key and email in config.json
- Supports filtering by:
  - Countries (ISO 3166-1 alpha-3 codes)
  - Event types
  - Date range

### FRED API
- Get API key from [FRED](https://fred.stlouisfed.org/docs/api/api_key.html)
- Provides economic indicators:
  - GDP growth rate
  - Inflation rate
  - Unemployment rate
  - Interest rates
  - Treasury rates
  - CPI changes

### CoinMarketCap API
- Get API key from [CoinMarketCap](https://coinmarketcap.com/api/)
- Provides cryptocurrency data:
  - Current prices
  - Market caps
  - 24h volumes
  - Price changes

### EOD Historical Data
- Get API key from [EODHD](https://eodhistoricaldata.com/cp/settings/api)
- Provides stock market data:
  - Real-time prices
  - Historical data
  - Company fundamentals

## Output Format

Questions are saved in JSON format:
```json
{
    "question": "Will [indicator] [change] to [value] by [date]?",
    "timeframe": "YYYY/MM/DD",
    "category": "[category]",
    "metric": "[metric]",
    "target_value": 123.45,
    "measurement_source": "[source]"
}
```

## Caching

- Data is cached to reduce API calls
- Default cache duration: 24 hours
- Cache location: ./cache/
- Separate caches for each data source

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
