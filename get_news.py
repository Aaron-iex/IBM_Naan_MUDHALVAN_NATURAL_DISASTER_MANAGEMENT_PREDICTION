# get_news.py
import requests
import os
from dotenv import load_dotenv

load_dotenv()

NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")
NEWSAPI_ENDPOINT = "https://newsapi.org/v2/everything" # Or /top-headlines

def get_disaster_news(query, language='en', sources=None, page_size=10, sort_by='relevancy'):
    """ Fetches news articles related to a query from NewsAPI. """
    if not NEWSAPI_KEY:
        return {"error": "NewsAPI Key not found in .env file"}

    headers = {'Authorization': f'Bearer {NEWSAPI_KEY}'}
    params = {
        'q': query, # Your search query (e.g., "India flood OR cyclone")
        'language': language,
        'pageSize': page_size,
        'sortBy': sort_by, # 'relevancy', 'popularity', 'publishedAt'
    }
    if sources: # e.g., 'bbc-news,the-times-of-india'
        params['sources'] = sources

    try:
        response = requests.get(NEWSAPI_ENDPOINT, headers=headers, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        if data.get('status') != 'ok':
            return {"error": f"NewsAPI Error: {data.get('code')} - {data.get('message')}"}

        articles = []
        for article in data.get('articles', []):
            articles.append({
                'title': article.get('title'),
                'source': article.get('source', {}).get('name'),
                'description': article.get('description'),
                'url': article.get('url'),
                'published_at': article.get('publishedAt')
            })
        return {"total_results": data.get('totalResults'), "articles": articles}

    except requests.exceptions.RequestException as e:
         print(f"Error fetching NewsAPI data: {e}")
         return {"error": f"Network error fetching news data: {e}"}
    except Exception as e:
         print(f"Error processing NewsAPI data: {e}")
         return {"error": f"Error processing news data: {e}"}

if __name__ == "__main__":
    # Example search (use specific terms like cyclone names, flood locations)
    news = get_disaster_news(query='India flood OR India cyclone OR India heatwave OR earthquake', page_size=5)
    import json
    print(json.dumps(news, indent=2))
