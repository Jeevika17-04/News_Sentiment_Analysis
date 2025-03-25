import logging
import os
import requests
import warnings
from bs4 import BeautifulSoup
from transformers import pipeline
from deep_translator import GoogleTranslator
from gtts import gTTS
from django.conf import settings

warnings.filterwarnings("ignore", category=UserWarning, message="TypedStorage is deprecated")
logger = logging.getLogger(__name__)

def scrape_news(company):
    """
    (Optional) If you still want Google News RSS scraping:
    """
    ...

# Pre-load NLP models once
sentiment_pipeline = pipeline("sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english")
summarizer = pipeline("summarization", model="sshleifer/distilbart-cnn-12-6")

def analyze_sentiment(text):
    try:
        if not text.strip():
            return "Neutral"
        result = sentiment_pipeline(text[:512])
        label = result[0]['label']
        return "Positive" if label == "POSITIVE" else "Negative"
    except Exception as e:
        logger.error(f"Sentiment analysis failed: {str(e)}")
        return "Neutral"

def summarize(text):
    try:
        words = text.split()
        if len(words) < 30:
            return text
        input_length = len(words)
        max_length = min(150, input_length - 10)
        min_length = max(30, input_length // 4)
        summary = summarizer(text, max_length=max_length, min_length=min_length, do_sample=False)[0]['summary_text']
        return summary
    except Exception as e:
        logger.error(str(e))
        return text[:150] + "..."

def analyze_articles(articles):
    """
    Performs comparative analysis on a list of articles.
    Returns sentiment distribution, common topics, dynamic coverage differences,
    and a final sentiment analysis string.
    """
    try:
        if not articles:
            return {"error": "No articles to analyze"}

        sentiment_counts = {"Positive": 0, "Negative": 0, "Neutral": 0}
        all_topics = []

        # Track which articles are positive/negative
        pos_titles = []
        neg_titles = []

        for article in articles:
            sentiment = article.get('sentiment', 'Neutral')
            if sentiment in sentiment_counts:
                sentiment_counts[sentiment] += 1
            else:
                sentiment_counts["Neutral"] += 1

            title = article.get('title', '')
            if sentiment == "Positive":
                pos_titles.append(title)
            elif sentiment == "Negative":
                neg_titles.append(title)

            # Extract top words from the title as "topics"
            topics = [word.strip().lower() for word in title.split()[:3] if word.strip()]
            all_topics.extend(topics)

        # Count the top 3 topics
        topic_counter = {}
        for topic in all_topics:
            topic_counter[topic] = topic_counter.get(topic, 0) + 1
        common_topics = sorted(topic_counter.items(), key=lambda x: x[1], reverse=True)[:3]
        common_topics = [topic[0].title() for topic in common_topics]

        # Build dynamic coverage differences
        coverage_differences = []
        coverage_differences.append(f"{sentiment_counts['Positive']} articles highlight positive developments")
        coverage_differences.append(f"{sentiment_counts['Negative']} articles discuss challenges/risks")

        # For more detail, list a couple of positive/negative article titles if available
        if pos_titles:
            coverage_differences.append(f"Positive articles include: {', '.join(pos_titles[:2])}")
        if neg_titles:
            coverage_differences.append(f"Negative articles include: {', '.join(neg_titles[:2])}")

        # Determine final sentiment
        if sentiment_counts["Positive"] > sentiment_counts["Negative"]:
            overall_sentiment = "News coverage is mostly positive."
        elif sentiment_counts["Negative"] > sentiment_counts["Positive"]:
            overall_sentiment = "News coverage is mostly negative."
        else:
            overall_sentiment = "Overall news coverage appears balanced."

        return {
            "sentiment_distribution": sentiment_counts,
            "common_topics": common_topics,
            "coverage_differences": coverage_differences,
            "final_sentiment_analysis": overall_sentiment
        }
    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}")
        return {"error": "Analysis failed"}

def generate_tts(company_name, analysis_data):
    """
    Converts the provided analysis data into a dynamic Hindi speech summary.
    
    The summary is built dynamically using:
      - Company Name.
      - Overall Sentiment (analysis_data['final_sentiment_analysis']).
      - Sentiment Distribution (from analysis_data['sentiment_distribution']).
      - Common Topics (from analysis_data['common_topics']).
      - Key Insights (from analysis_data['coverage_differences']), formatted as an ordered list.
    
    It then translates this summary into Hindi, generates a unique audio file in the media directory,
    and returns the filename.
    """
    try:
        if not analysis_data or not isinstance(analysis_data, dict):
            logger.error("Invalid analysis_data provided to generate_tts()")
            return None

        media_dir = settings.MEDIA_ROOT
        os.makedirs(media_dir, exist_ok=True)

        sentiment_summary = analysis_data.get("final_sentiment_analysis", "No sentiment analysis available")
        sentiment_dist = analysis_data.get("sentiment_distribution", {})
        common_topics = analysis_data.get("common_topics", [])
        coverage_diff = analysis_data.get("coverage_differences", [])

        # Build the dynamic summary text with an ordered list for key insights
        summary_text = (
            f"Company: {company_name}. "
            f"Overall Sentiment: {sentiment_summary}. "
            f"Positive articles: {sentiment_dist.get('Positive', 0)}, "
            f"Negative articles: {sentiment_dist.get('Negative', 0)}, "
            f"Neutral articles: {sentiment_dist.get('Neutral', 0)}. "
        )
        if common_topics:
            summary_text += "Common topics include " + ", ".join(common_topics) + ". "
        if coverage_diff:
            # Format key insights as an ordered list using numbers
            insights = []
            for i, insight in enumerate(coverage_diff, start=1):
                insights.append(f"{i}. {insight}")
            insights_text = "Key insights are: " + " ".join(insights) + ". "
            summary_text += insights_text

        logger.info(f"Generated summary text: {summary_text}")

        # Translate the summary text into Hindi
        translated_text = GoogleTranslator(source='auto', target='hi').translate(summary_text)
        logger.info(f"Translated text: {translated_text}")

        # Generate a unique filename using the company name and a hash of the summary text
        filename = f"{company_name.replace(' ', '_')}_{hash(summary_text)}.mp3"
        file_path = os.path.join(media_dir, filename)
        logger.info(f"Saving TTS audio to: {file_path}")

        # Generate the TTS audio file using gTTS (Hindi)
        tts = gTTS(translated_text, lang='hi')
        tts.save(file_path)

        if os.path.exists(file_path):
            logger.info(f"TTS file created: {file_path}")
            return filename
        else:
            logger.error(f"TTS file was not created: {file_path}")
            return None
    except Exception as e:
        logger.error(f"TTS generation error: {str(e)}")
        return None
