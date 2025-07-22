def get_blog_plan_prompt(keyword: str, language: str = "en") -> str:
    """
    Generate the blog plan prompt for OpenAI
    """
    return f"""Create a comprehensive, SEO-friendly blog plan for the article: "{keyword}" in {language}.

IMPORTANT: You are rephrasing and expanding an existing article, not creating a new topic.

Return the response in JSON format with the following structure:
{{
    "title": "Rephrased, SEO-friendly version of the original title",
    "category": "Main category for the blog",
    "table_of_contents": [
        {{
            "heading": "Descriptive, SEO-friendly main heading",
            "subheadings": [
                "Descriptive, SEO-friendly subheading",
                "Another subheading"
            ]
        }},
        ...
    ],
    "headings": [
        {{
            "title": "Descriptive, SEO-friendly main heading",
            "description": "Brief description of what this section will cover",
            "subheadings": [
                {{
                    "title": "Descriptive, SEO-friendly subheading",
                    "description": "What this sub-section covers"
                }},
                ...
            ]
        }},
        ...
    ],
    "image_prompts": [
        {{
            "prompt": "Detailed, realistic prompt for first image that matches the article content",
            "purpose": "Purpose of this image in the blog"
        }},
        {{
            "prompt": "Detailed, realistic prompt for second image that matches the article content",
            "purpose": "Purpose of this image in the blog"
        }}
    ]
}}

Requirements:
- Title should be a rephrased, SEO-friendly version of the original article title
- Category should be specific and relevant to the article topic
- There MUST be at least 6 to 7 main headings, each with 2–3 descriptive, SEO-friendly subheadings
- The table_of_contents must list all main headings and their subheadings using their descriptive titles
- The headings section must provide a description for each main heading and each subheading
- Image prompts MUST be detailed and specific to the article content (generate exactly two prompts)
- Image prompts should describe realistic images that would accompany this type of article
- All content should be in {language}
- Do NOT use generic numbering (like 1.1, 2.1, etc.) in any heading or subheading titles
- Focus on expanding and rephrasing the original article content

Return ONLY the JSON structure, nothing else.""" 