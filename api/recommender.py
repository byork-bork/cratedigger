# api/recommender.py
from collections import defaultdict
from datetime import datetime
from .models import ListeningSession, Album

# Map weather conditions → moods they complement
WEATHER_MOOD_MAP = {
    'rainy':  ['calm', 'sad', 'focused', 'neutral'],
    'sunny':  ['happy', 'energized', 'neutral'],
    'cloudy': ['neutral', 'tired', 'calm'],
    'cold':   ['calm', 'focused', 'tired'],
    'warm':   ['happy', 'energized'],
    'stormy': ['anxious', 'stressed', 'energized'],
    'snowy':  ['calm', 'happy', 'focused'],
}

def get_season(month):
    if month in (12, 1, 2):  return 'winter'
    if month in (3, 4, 5):   return 'spring'
    if month in (6, 7, 8):   return 'summer'
    return 'fall'

def recommend_album(user, mood, weather=None, now=None):
    """
    Returns the best-matching Album instance for the given context,
    or None if there's not enough data.

    Args:
        user:    Django User instance
        mood:    str, one of the EMOTION_CHOICES keys e.g. 'calm'
        weather: str or None, e.g. 'rainy'
        now:     datetime or None (defaults to current time)
    """
    if now is None:
        now = datetime.now()

    hour        = now.hour
    dow         = now.weekday()   # 0=Mon, 6=Sun
    month       = now.month
    season      = get_season(month)
    is_weekend  = dow >= 5

    # Fetch all sessions for this user with enough data
    sessions = (
        ListeningSession.objects
        .filter(user=user)
        .select_related('album')
    )

    if not sessions.exists():
        return None

    # Build per-album scores
    scores = defaultdict(float)
    album_map = {}

    for session in sessions:
        album = session.album
        album_map[album.id] = album
        s = 0.0

        # 1. Mood match (weight: 5) — core signal
        if session.pre_emotion == mood:
            s += 5.0

        # 2. Complementary weather mood (weight: 2)
        if weather and weather in WEATHER_MOOD_MAP:
            if session.pre_emotion in WEATHER_MOOD_MAP[weather]:
                s += 2.0

        # 3. Time of day proximity (weight: 1.5)
        #    Full score if within 2 hours, decays linearly to 0 at 6 hours
        hour_diff = abs(session.hour_of_day - hour)
        hour_diff = min(hour_diff, 24 - hour_diff)  # wrap around midnight
        if hour_diff <= 6:
            s += 1.5 * (1 - hour_diff / 6)

        # 4. Weekday/weekend match (weight: 1)
        session_is_weekend = session.day_of_week >= 5
        if session_is_weekend == is_weekend:
            s += 1.0

        # 5. Season match (weight: 1.5)
        if get_season(session.month) == season:
            s += 1.5

        scores[album.id] += s

    if not scores:
        return None

    # Sort albums by score descending, return the top one
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    best_album_id = ranked[0][0]
    return album_map[best_album_id]