import json
from datetime import datetime

def save_questions(questions, base_filename=None):
    """Save questions to a JSON file with analytics."""
    if not questions:
        print("No questions to save.")
        return
    
    # Get current date and time
    current_time = datetime.now()
    
    # Format filename with date and time
    if base_filename:
        filename = f'{base_filename}_{current_time.strftime("%Y-%m-%d-%H-%M")}.json'
    else:
        filename = f'financial_questions_{current_time.strftime("%Y-%m-%d-%H-%M")}.json'
    
    try:
        with open(filename, 'w', encoding='utf-8') as file:
            json.dump(questions, file, ensure_ascii=False, indent=4)
        
        print(f"\nGenerated {len(questions)} valid unique questions within the specified date range.")
        print(f"Questions saved to {filename}")
        
        # Analyze question distribution
        categories = {}
        metrics = {}
        companies = set()
        timeframes = set()
        
        for q in questions:
            cat = q.get('category', 'unknown')
            metric = q.get('metric', 'unknown')
            company = q.get('company', None)
            timeframe = q.get('timeframe', None)
            
            categories[cat] = categories.get(cat, 0) + 1
            metrics[metric] = metrics.get(metric, 0) + 1
            if company:
                companies.add(company)
            if timeframe:
                timeframes.add(timeframe)
        
        print("\nQUESTION ANALYSIS:")
        print("\nCategories breakdown:")
        for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
            print(f"- {cat}: {count} questions ({count/len(questions)*100:.1f}%)")
        
        print("\nMetrics breakdown:")
        for metric, count in sorted(metrics.items(), key=lambda x: x[1], reverse=True):
            print(f"- {metric}: {count} questions ({count/len(questions)*100:.1f}%)")
        
        print(f"\nUnique companies mentioned: {len(companies)}")
        print(f"Unique timeframes used: {len(timeframes)}")
        
    except Exception as e:
        print(f"Error saving questions to file: {e}")
