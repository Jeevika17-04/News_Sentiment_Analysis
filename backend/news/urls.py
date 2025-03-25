from django.urls import path
from . import api

urlpatterns = [
    path('get_news/', api.get_news, name='get_news'),
    path('analyze/', api.analyze, name='analyze'),
    path('tts/', api.tts, name='tts'),
]
