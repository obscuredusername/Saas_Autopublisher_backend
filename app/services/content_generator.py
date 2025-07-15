import os
import json
import re
import openai
from typing import Dict, Any, Optional, List
from app.prompts.blog_content_prompt import get_blog_content_prompt
from app.prompts.blog_plan_prompt import get_blog_plan_prompt

class ContentGenerator:
    def __init__(self):
        self.client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    async def generate_blog_plan(self, keyword: str, language: str = "en") -> Dict[str, Any]:
        """
        Generate a comprehensive blog plan including title, headings, category, and image prompts
        """
        try:
            blog_plan_prompt = get_blog_plan_prompt(keyword, language)

            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a professional blog planner and content strategist. You excel at creating comprehensive blog structures and creative content plans. Always respond with valid JSON only."},
                    {"role": "user", "content": blog_plan_prompt}
                ],
                temperature=0.7
            )
            
            # Debug: Print the raw LLM response
            raw_response = response.choices[0].message.content
            print(f"\n=== RAW LLM RESPONSE for '{keyword}' in '{language}' ===\n{raw_response}\n====================\n")
            
            # Parse the response as JSON
            try:
                blog_plan = json.loads(raw_response.strip())
                print(f"\n📝 Parsed Blog Plan for '{keyword}' in '{language}':\n{json.dumps(blog_plan, indent=2)}\n")
                
                # Validate and fix blog plan if needed
                if not isinstance(blog_plan, dict):
                    print(f"❌ Blog plan is not a dictionary")
                    return None
                
                # Ensure required fields exist
                if not blog_plan.get("title"):
                    blog_plan["title"] = keyword
                
                if not blog_plan.get("headings") or not isinstance(blog_plan["headings"], list):
                    print(f"❌ Blog plan missing or invalid headings")
                    return None
                
                if not blog_plan.get("image_prompts") or not isinstance(blog_plan["image_prompts"], list):
                    print(f"❌ Blog plan missing or invalid image_prompts")
                    return None
                
                # If image prompts are empty or generic, generate better ones
                if not blog_plan["image_prompts"] or all(prompt.get("prompt", "").startswith("Professional image") for prompt in blog_plan["image_prompts"]):
                    print(f"🔄 Generating specific image prompts for '{keyword}'...")
                    blog_plan["image_prompts"] = await self.generate_image_prompts(keyword, language)
                
                # ALWAYS ensure we have at least 2 image prompts based on the title
                if not blog_plan["image_prompts"] or len(blog_plan["image_prompts"]) < 2:
                    print(f"🔄 Creating image prompts from title: '{blog_plan.get('title', keyword)}'")
                    blog_plan["image_prompts"] = self.create_image_prompts_from_title(blog_plan.get('title', keyword), keyword)
                
                print(f"✅ Validated blog plan with {len(blog_plan['headings'])} headings and {len(blog_plan['image_prompts'])} image prompts")
                return blog_plan
                
            except json.JSONDecodeError as e:
                print(f"❌ Error parsing blog plan JSON: {str(e)}")
                print(f"Raw response: {raw_response}")
                return None
            
        except Exception as e:
            print(f"❌ Error generating blog plan: {str(e)}")
            return None

    async def generate_blog_content(
        self, 
        keyword: str, 
        language: str, 
        blog_plan: Dict[str, Any], 
        video_info: Optional[Dict[str, Any]], 
        category_names: List[str], 
        section_chunks: Dict[str, List[str]], 
        custom_length_prompt: str = "",
        target_word_count: int = 2000
    ) -> Dict[str, Any]:
        """
        Generate blog content using OpenAI API
        """
        try:
            content_prompt = get_blog_content_prompt(
                keyword=keyword,
                language=language,
                blog_plan=blog_plan,
                video_info=video_info,
                category_names=category_names,
                section_chunks=section_chunks
            )
            
            # Add custom length prompt if provided
            if custom_length_prompt:
                content_prompt = custom_length_prompt + "\n\n" + content_prompt
            
            # Calculate max_tokens based on target length (roughly 1.3 tokens per word)
            max_tokens = min(int(target_word_count * 1.5), 4000)  # Cap at 4000 tokens
            
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": (
                        "You are a professional content writer specializing in creating comprehensive, well-researched blog posts. "
                        "You MUST ALWAYS start your response with a category selection in the format 'SELECTED_CATEGORY: [category name]' before writing any content. "
                        "DO NOT include any h1 tags in your content - the title is provided separately. "
                        "IMPORTANT: Your entire response MUST be in valid HTML markup (not Markdown, not plain text). Use <h2>, <h3>, <p>, <ul>, <li>, <img>, <blockquote>, <strong>, <em>, etc. as appropriate. "
                        "Do not use any Markdown formatting. Return only HTML markup for the blog content."
                    )},
                    {"role": "user", "content": content_prompt + "\n\nIMPORTANT: Return the blog content in valid HTML markup only. Do not use Markdown or plain text formatting. Use <h2>, <h3>, <p>, <ul>, <li>, <img>, <blockquote>, <strong>, <em>, etc. as appropriate. Do not include <h1> tags. Return only HTML."}
                ],
                temperature=0.7,
                max_tokens=max_tokens
            )
            
            generated_content = response.choices[0].message.content.strip()
            print("\n===== GENERATED CONTENT =====\n", generated_content[:2000], "\n============================\n")
            
            # Extract selected category
            selected_category_name = None
            lines = generated_content.splitlines()
            for i, line in enumerate(lines[:5]):
                if line.strip().startswith("SELECTED_CATEGORY:"):
                    selected_category_name = line.replace("SELECTED_CATEGORY:", "").strip()
                    lines.pop(i)
                    generated_content = "\n".join(lines).lstrip()
                    break
            
            # Remove any h1 tags
            generated_content = re.sub(r'<h1>.*?</h1>', '', generated_content, flags=re.DOTALL)
            
            # Calculate word count
            word_count = len(generated_content.split())
            
            return {
                "success": True,
                "content": generated_content,
                "word_count": word_count,
                "selected_category_name": selected_category_name
            }
            
        except Exception as e:
            print(f"❌ Error generating blog content: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "content": "",
                "word_count": 0,
                "selected_category_name": None
            }

    async def generate_image_prompts(self, keyword: str, language: str = "en") -> List[Dict[str, str]]:
        """
        Generate specific image prompts for a given keyword
        """
        try:
            image_prompt_request = f"""Generate two detailed, realistic image prompts for an article about: "{keyword}"

The images should be:
1. Professional and relevant to the article topic
2. Realistic and suitable for a blog post
3. Descriptive enough for image generation

Return ONLY a JSON array with exactly 2 image prompt objects:
[
    {{
        "prompt": "Detailed description of first image",
        "purpose": "Purpose of this image in the article"
    }},
    {{
        "prompt": "Detailed description of second image", 
        "purpose": "Purpose of this image in the article"
    }}
]

Make the prompts specific to the topic and avoid generic descriptions."""

            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert at creating detailed, realistic image prompts for blog articles. Always respond with valid JSON only."},
                    {"role": "user", "content": image_prompt_request}
                ],
                temperature=0.7
            )
            
            raw_response = response.choices[0].message.content.strip()
            try:
                image_prompts = json.loads(raw_response)
                if isinstance(image_prompts, list) and len(image_prompts) >= 2:
                    return image_prompts[:2]  # Return only first 2 prompts
                else:
                    print(f"⚠️ Invalid image prompts format, using fallback")
                    return self.get_fallback_image_prompts(keyword)
            except json.JSONDecodeError:
                print(f"⚠️ Error parsing image prompts JSON, using fallback")
                return self.get_fallback_image_prompts(keyword)
                
        except Exception as e:
            print(f"❌ Error generating image prompts: {str(e)}")
            return self.get_fallback_image_prompts(keyword)

    def get_fallback_image_prompts(self, keyword: str) -> List[Dict[str, str]]:
        """
        Provide fallback image prompts when generation fails
        """
        return [
            {
                "prompt": f"Professional photograph related to {keyword}, high quality, editorial style",
                "purpose": "Main article image"
            },
            {
                "prompt": f"Infographic or diagram illustrating key concepts about {keyword}, clean design",
                "purpose": "Supporting visual content"
            }
        ]

    def create_image_prompts_from_title(self, title: str, original_keyword: str) -> List[Dict[str, str]]:
        """
        Create specific image prompts based on the title and original keyword
        """
        # Extract key concepts from title and keyword
        title_lower = title.lower()
        keyword_lower = original_keyword.lower()
        
        # Common product/tech keywords that suggest specific image types
        if any(word in title_lower or word in keyword_lower for word in ['kindle', 'tablet', 'device', 'phone', 'laptop']):
            return [
                {
                    "prompt": f"Professional product photography of {original_keyword}, clean background, high resolution, editorial style",
                    "purpose": "Main product showcase image"
                },
                {
                    "prompt": f"Comparison chart or infographic showing {original_keyword} features and benefits, modern design",
                    "purpose": "Feature comparison visual"
                }
            ]
        elif any(word in title_lower or word in keyword_lower for word in ['deal', 'sale', 'discount', 'price', 'offer']):
            return [
                {
                    "prompt": f"Price tag or discount banner with {original_keyword}, shopping concept, professional photography",
                    "purpose": "Deal/pricing visual"
                },
                {
                    "prompt": f"Comparison of original vs discounted prices for {original_keyword}, savings visualization",
                    "purpose": "Savings comparison chart"
                }
            ]
        elif any(word in title_lower or word in keyword_lower for word in ['amazon', 'prime', 'shopping']):
            return [
                {
                    "prompt": f"Amazon Prime Day shopping concept with {original_keyword}, e-commerce theme, professional photography",
                    "purpose": "Prime Day shopping visual"
                },
                {
                    "prompt": f"Online shopping cart or wishlist with {original_keyword}, digital commerce interface",
                    "purpose": "E-commerce interface visual"
                }
            ]
        else:
            # Generic but specific prompts based on the title
            return [
                {
                    "prompt": f"Professional editorial image representing '{title}', high quality photography, relevant to the topic",
                    "purpose": "Main article image"
                },
                {
                    "prompt": f"Infographic or diagram related to '{original_keyword}', clean modern design, informative visual",
                    "purpose": "Supporting informational visual"
                }
            ] 