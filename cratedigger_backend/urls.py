# cratedigger_backend/urls.py
from django.contrib import admin
from django.urls import path
from api.views import get_collection, log_session, get_release_details, get_recommendation, get_mood_tags

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/collection/<str:username>/',  get_collection),
    path('api/log-session/',                log_session),
    path('api/release/<int:release_id>/',   get_release_details),
    path('api/recommend/',                  get_recommendation),
    path('api/mood-tags/',                  get_mood_tags),
]