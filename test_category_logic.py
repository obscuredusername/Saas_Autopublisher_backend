#!/usr/bin/env python3
"""
Test script to debug category selection logic directly
"""

import asyncio
import json
from app.content_generator import ContentGenerator

async def test_category_selection_logic():
    """Test the category selection logic directly"""
    
    print("🧪 Testing Category Selection Logic Directly")
    print("=" * 60)
    
    # Create content generator
    content_generator = ContentGenerator()
    
    # Test with sample data
    sample_data = {
        'search_info': {
            'keyword': 'elon musk',
            'language': 'en'
        },
        'scraped_content': [
            {
                'title': 'Elon Musk Biography',
                'content': 'Elon Musk is a business magnate and investor...',
                'url': 'https://example.com/elon-musk'
            }
        ],
        'blog_plan': {
            'title': 'Elon Musk: The Visionary Entrepreneur',
            'headings': [
                {'title': 'Early Life', 'description': 'Early life and education'},
                {'title': 'Career', 'description': 'Professional career'}
            ],
            'image_prompts': [
                {'prompt': 'Elon Musk portrait', 'purpose': 'Main image'},
                {'prompt': 'Tesla factory', 'purpose': 'Context image'}
            ]
        },
        'category_names': ['Biography', 'Technology', 'Business', 'Science', 'Innovation']
    }
    
    print(f"📋 Test data:")
    print(f"   - Keyword: {sample_data['search_info']['keyword']}")
    print(f"   - Available categories: {sample_data['category_names']}")
    
    # Test the category selection instruction generation
    category_list_str = ', '.join(sample_data['category_names'])
    category_selection_instruction = f"""
Here is a list of available categories: [{category_list_str}].
Select the most relevant category for this content and return ONLY the category name as:
SELECTED_CATEGORY: <category name>
Place this line at the very top of your response, then provide the full content below.
"""
    
    print(f"\n🎯 Category Selection Instruction:")
    print(category_selection_instruction)
    
    # Test parsing logic
    test_responses = [
        "SELECTED_CATEGORY: Biography\n\n<article>Content here...</article>",
        "SELECTED_CATEGORY: Technology\n\n<article>Content here...</article>",
        "<article>Content here...</article>",  # No category selected
        "Biography\n\n<article>Content here...</article>",  # Wrong format
    ]
    
    print(f"\n🔍 Testing Response Parsing:")
    for i, response in enumerate(test_responses, 1):
        print(f"\n   Test {i}:")
        print(f"   Response: {response[:50]}...")
        
        lines = response.splitlines()
        selected_category_name = None
        
        if lines and lines[0].startswith("SELECTED_CATEGORY:"):
            selected_category_name = lines[0].replace("SELECTED_CATEGORY:", "").strip()
            print(f"   ✅ Selected category: {selected_category_name}")
        else:
            print(f"   ❌ No SELECTED_CATEGORY found")
    
    # Test category matching logic
    print(f"\n🎯 Testing Category Matching:")
    categories = [
        {'_id': '1', 'name': 'Biography'},
        {'_id': '2', 'name': 'Technology'},
        {'_id': '3', 'name': 'Business'},
        {'_id': '4', 'name': 'Science'},
        {'_id': '5', 'name': 'Innovation'}
    ]
    
    test_selected_categories = ['Biography', 'Technology', 'business', 'Unknown Category']
    
    for selected in test_selected_categories:
        print(f"\n   Testing: '{selected}'")
        category_ids = []
        
        for cat in categories:
            if cat['name'].strip().lower() == selected.strip().lower():
                category_ids = [str(cat['_id'])]
                print(f"   ✅ Matched: {cat['name']} (ID: {cat['_id']})")
                break
        else:
            print(f"   ❌ No match found for '{selected}'")
    
    print(f"\n✅ Category selection logic test completed!")

if __name__ == "__main__":
    asyncio.run(test_category_selection_logic()) 