#!/usr/bin/env python3
"""
Simple test to check category selection with actual database categories
"""

import asyncio
from app.content_generator import ContentGenerator

async def test_category_selection():
    """Test category selection with actual categories"""
    
    print("🧪 Testing Category Selection with Actual Categories")
    print("=" * 60)
    
    # Create content generator
    content_generator = ContentGenerator()
    
    # Use the actual categories from your database
    category_names = ['bio broly', 'A LA UNE', 'SCI-TECH', 'SANTE', 'POLITIQUE', 'ECONOMIE', 'MONDE', 'DIVERTISSEMENT', 'SPORT']
    
    print(f"📋 Available categories: {category_names}")
    
    # Test the category selection instruction
    category_list_str = ', '.join(category_names)
    category_selection_instruction = f"""
IMPORTANT: You must select a category from this list: [{category_list_str}]

Return your response in this EXACT format:
SELECTED_CATEGORY: [category name from the list above]

Then provide the full content below. The category selection MUST be the first line.
"""
    
    print(f"\n🎯 Category Selection Instruction:")
    print(category_selection_instruction)
    
    # Test different AI responses
    test_responses = [
        "SELECTED_CATEGORY: SCI-TECH\n\n<article>Content about technology...</article>",
        "SELECTED_CATEGORY: POLITIQUE\n\n<article>Content about politics...</article>",
        "SELECTED_CATEGORY: bio broly\n\n<article>Content about bio...</article>",
        "<article>Content without category...</article>",  # No category
        "SCI-TECH\n\n<article>Content with category on first line...</article>",  # Wrong format
    ]
    
    print(f"\n🔍 Testing Response Parsing:")
    for i, response in enumerate(test_responses, 1):
        print(f"\n   Test {i}:")
        print(f"   Response: {response[:50]}...")
        
        lines = response.splitlines()
        selected_category_name = None
        
        # Try to find SELECTED_CATEGORY in the first few lines
        for j, line in enumerate(lines[:5]):
            if line.strip().startswith("SELECTED_CATEGORY:"):
                selected_category_name = line.replace("SELECTED_CATEGORY:", "").strip()
                print(f"   ✅ Selected category: {selected_category_name}")
                break
        else:
            print(f"   ❌ No SELECTED_CATEGORY found in first 5 lines")
            # Try to find any category-like line
            for j, line in enumerate(lines[:3]):
                line_stripped = line.strip()
                if line_stripped and not line_stripped.startswith('<') and len(line_stripped.split()) <= 3:
                    potential_category = line_stripped
                    if potential_category in category_names:
                        selected_category_name = potential_category
                        print(f"   ✅ Found potential category: {selected_category_name}")
                        break
        
        if selected_category_name:
            print(f"   🎯 Final selected category: {selected_category_name}")
        else:
            print(f"   ❌ No category selected")
    
    print(f"\n✅ Category selection test completed!")

if __name__ == "__main__":
    asyncio.run(test_category_selection()) 