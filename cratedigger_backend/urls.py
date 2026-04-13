# cratedigger_backend/urls.py
from django.contrib import admin
from django.urls import path
from api.views import (
    login_user,
    log_session,
    get_release_details,
    get_recommendation,
    get_mood_tags,
    get_history,
)

urlpatterns = [
    path('admin/',                          admin.site.urls),
    path('api/login/',                      login_user),
    path('api/log-session/',                log_session),
    path('api/release/<int:release_id>/',   get_release_details),
    path('api/recommend/',                  get_recommendation),
    path('api/mood-tags/',                  get_mood_tags),
    path('api/history/',                    get_history),
]