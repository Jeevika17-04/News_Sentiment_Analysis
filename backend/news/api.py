from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
import logging
import requests
from django.conf import settings
from .utils import analyze_sentiment, summarize, analyze_articles, generate_tts
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

@api_view(['POST'])
def get_news(request):
    """
    Fetches news articles for a given company using NewsAPI.
    Now fetching up to 20 articles to ensure we have enough data.
    """
    try:
        company_name = request.data.get('company_name', '').strip()
        if not company_name:
            return Response({"error": "company_name is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        NEWS_API_KEY = settings.NEWS_API_KEY
        url = "https://newsapi.org/v2/everything"
        params = {
            'q': company_name,
            'apiKey': NEWS_API_KEY,
            'pageSize': 20,  # Increased from 10 to 20
            'language': 'en',
            'sortBy': 'relevancy'
        }
        
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        news_data = response.json()

        if news_data.get("status") != "ok" or not news_data.get("articles"):
            return Response({"error": "No articles found or API error"}, status=status.HTTP_404_NOT_FOUND)

        articles = []
        for article in news_data.get('articles', []):
            summary = article.get('description') or ''
            articles.append({
                'title': article.get('title', ''),
                'summary': summary,
                'link': article.get('url', ''),
                'source': article.get('source', {}).get('name', '')
            })

        # Process articles for sentiment and summarization concurrently
        def process_article(article):
            article['sentiment'] = analyze_sentiment(article['summary'])
            article['summary'] = summarize(article['summary'])
            return article

        with ThreadPoolExecutor() as executor:
            articles = list(executor.map(process_article, articles))

        return Response({
            "status": "success",
            "company": company_name,
            "articles": articles,
            "count": len(articles)
        })
    except requests.exceptions.RequestException as e:
        logger.error(f"NewsAPI request failed: {str(e)}")
        return Response({"error": "Failed to fetch news from NewsAPI"}, status=status.HTTP_502_BAD_GATEWAY)
    except Exception as e:
        logger.error(str(e))
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def analyze(request):
    """
    Performs comparative analysis on provided articles.
    """
    try:
        articles = request.data.get('articles', [])
        if not articles:
            return Response({"error": "No articles provided"}, status=status.HTTP_400_BAD_REQUEST)

        # Preprocess each article (sentiment, summarization already done in get_news)
        analyzed_articles = articles[:]  # We can reuse them directly

        comparative = analyze_articles(analyzed_articles)
        return Response({
            "articles": analyzed_articles,
            "comparative": comparative
        })
    except Exception as e:
        logger.error(str(e))
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def tts(request):
    """
    Generates a Hindi TTS audio file for the provided analysis data.
    Expects:
      - company_name: The company name.
      - analysis: A dictionary containing the comparative analysis.
    """
    try:
        company_name = request.data.get('company_name', '').strip()
        analysis_data = request.data.get('analysis')

        if not company_name:
            return Response({"error": "company_name is required"}, status=status.HTTP_400_BAD_REQUEST)
        if not analysis_data:
            return Response({"error": "Analysis data is required"}, status=status.HTTP_400_BAD_REQUEST)

        audio_filename = generate_tts(company_name, analysis_data)
        if not audio_filename:
            return Response({"error": "TTS generation failed"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Build an absolute URL for the audio file
        audio_url = request.build_absolute_uri(f"{settings.MEDIA_URL}{audio_filename}")
        return Response({"audio_url": audio_url})
    except Exception as e:
        logger.error(str(e))
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
