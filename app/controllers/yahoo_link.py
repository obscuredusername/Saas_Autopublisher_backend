class YahooLinkController:
    def __init__(self):
        pass

    async def yahoo_link(self, category: str, language: str):
        category = category.lower()
        language = language.lower()
        # Determine subdomain
        if language == 'en':
            subdomain = 'www'
        else:
            subdomain = language
        if category == 'finance':
            return f"https://{subdomain}.finance.yahoo.com"
        else:
            return f"https://{subdomain}.yahoo.com/news/{category}"

    @staticmethod
    def valid_categories():
        return ["news", "finance", "business", "fashion", "lifestyle", "world"]
         