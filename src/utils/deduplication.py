import re
from datetime import datetime

def normalize_value(value):
    """Normalize numeric value for comparison."""
    try:
        if isinstance(value, str):
            # Remove currency symbols and commas
            value = value.replace('$', '').replace(',', '')
        return float(value)
    except (ValueError, TypeError):
        return value

def check_question_similarity(question1, question2, similarity_threshold=0.8):
    """Check similarity between two questions with improved comparison."""
    # Exact match
    if question1['question'] == question2['question']:
        return True
    
    # Compare essential fields
    if question1.get('category') != question2.get('category'):
        return False
        
    # Compare metrics
    if question1.get('metric') == question2.get('metric'):
        # Compare target values with tolerance
        val1 = normalize_value(question1.get('target_value'))
        val2 = normalize_value(question2.get('target_value'))
        if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
            # If values are within 10% of each other
            if abs(val1 - val2) / max(val1, val2) < 0.1:
                # Check timeframe proximity
                try:
                    date1 = datetime.strptime(question1.get('timeframe', ''), '%Y/%m/%d')
                    date2 = datetime.strptime(question2.get('timeframe', ''), '%Y/%m/%d')
                    # If dates are within 30 days
                    if abs((date1 - date2).days) < 30:
                        return True
                except ValueError:
                    pass
    
    # Compare company/asset specific questions
    if question1.get('category') in ['cryptocurrency', 'financial_market']:
        # Extract symbols/names from questions
        symbols1 = set(re.findall(r'\(([^)]+)\)', question1['question']))
        symbols2 = set(re.findall(r'\(([^)]+)\)', question2['question']))
        if symbols1 & symbols2:  # If there are common symbols
            return True
    
    # Compare social events questions
    if question1.get('category') == 'social_events':
        # Extract country codes
        countries1 = set(re.findall(r'\b[A-Z]{3}\b', question1['question']))
        countries2 = set(re.findall(r'\b[A-Z]{3}\b', question2['question']))
        if countries1 & countries2:  # If same country
            return True
    
    return False

def deduplicate_questions(questions):
    """Remove duplicate questions from the list with improved deduplication."""
    if not questions:
        return []
        
    unique_questions = []
    # Sort questions by category for more efficient comparison
    sorted_questions = sorted(questions, key=lambda x: (x.get('category', ''), x.get('metric', '')))
    
    for new_question in sorted_questions:
        is_duplicate = False
        # Only compare with questions in same category
        category_questions = [q for q in unique_questions if q.get('category') == new_question.get('category')]
        
        for existing_question in category_questions:
            if check_question_similarity(new_question, existing_question):
                is_duplicate = True
                break
        
        if not is_duplicate:
            unique_questions.append(new_question)
    
    return unique_questions 
