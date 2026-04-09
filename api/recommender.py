# api/recommender.py
from collections import defaultdict
from datetime import datetime

# ---------------------------------------------------------------------------
# Genre → compatible moods
# ---------------------------------------------------------------------------
GENRE_MOOD_MAP = {
    # Rock family
    'Rock':              ['energized', 'stressed', 'happy', 'neutral'],
    'Hard Rock':         ['energized', 'stressed'],
    'Punk':              ['stressed', 'energized', 'anxious'],
    'Alternative Rock':  ['neutral', 'sad', 'anxious', 'calm'],
    'Indie Rock':        ['neutral', 'calm', 'happy', 'sad'],
    'Psychedelic Rock':  ['calm', 'neutral', 'happy'],
    'Progressive Rock':  ['focused', 'neutral', 'calm'],
    'Folk Rock':         ['calm', 'sad', 'neutral', 'happy'],
    'Classic Rock':      ['happy', 'neutral', 'energized'],

    # Electronic
    'Electronic':        ['focused', 'energized', 'neutral'],
    'Ambient':           ['calm', 'tired', 'focused', 'anxious'],
    'Techno':            ['energized', 'stressed', 'focused'],
    'House':             ['happy', 'energized', 'neutral'],
    'Drum n Bass':       ['energized', 'stressed', 'anxious'],
    'IDM':               ['focused', 'neutral', 'calm'],
    'Downtempo':         ['calm', 'tired', 'neutral', 'sad'],
    'Trip Hop':          ['sad', 'calm', 'neutral', 'tired'],

    # Jazz
    'Jazz':              ['calm', 'neutral', 'happy', 'focused'],
    'Bebop':             ['focused', 'energized', 'neutral'],
    'Hard Bop':          ['energized', 'focused', 'happy'],
    'Cool Jazz':         ['calm', 'neutral', 'focused'],
    'Free Jazz':         ['anxious', 'stressed', 'energized'],
    'Fusion':            ['energized', 'focused', 'happy'],
    'Smooth Jazz':       ['calm', 'happy', 'neutral'],
    'Soul Jazz':         ['happy', 'calm', 'neutral'],
    'Modal Jazz':        ['focused', 'calm', 'neutral'],

    # Classical
    'Classical':         ['calm', 'focused', 'sad', 'neutral'],
    'Baroque':           ['focused', 'calm', 'neutral'],
    'Romantic':          ['sad', 'calm', 'happy', 'neutral'],
    'Contemporary':      ['neutral', 'focused', 'anxious'],
    'Opera':             ['sad', 'happy', 'energized'],
    'Chamber Music':     ['calm', 'focused', 'neutral'],

    # Soul / R&B / Funk
    'Soul':              ['happy', 'sad', 'calm', 'neutral'],
    'R&B':               ['happy', 'calm', 'sad', 'neutral'],
    'Funk':              ['happy', 'energized', 'neutral'],
    'Disco':             ['happy', 'energized', 'neutral'],
    'Neo Soul':          ['calm', 'sad', 'neutral', 'happy'],

    # Hip Hop
    'Hip Hop':           ['energized', 'happy', 'neutral', 'stressed'],
    'Rap':               ['energized', 'stressed', 'neutral'],
    'Lo-fi':             ['calm', 'tired', 'focused', 'neutral'],

    # Folk / Country / Americana
    'Folk':              ['calm', 'sad', 'happy', 'neutral'],
    'Country':           ['happy', 'sad', 'calm', 'neutral'],
    'Americana':         ['calm', 'sad', 'neutral'],
    'Bluegrass':         ['happy', 'energized', 'calm'],
    'Blues':             ['sad', 'calm', 'neutral'],

    # Metal
    'Metal':             ['stressed', 'energized', 'anxious'],
    'Heavy Metal':       ['stressed', 'energized'],
    'Death Metal':       ['stressed', 'anxious'],
    'Black Metal':       ['stressed', 'sad', 'anxious'],
    'Doom Metal':        ['sad', 'tired', 'anxious'],
    'Post-Metal':        ['sad', 'anxious', 'neutral'],

    # Pop
    'Pop':               ['happy', 'neutral', 'energized'],
    'Synth-pop':         ['happy', 'energized', 'neutral'],
    'Dream Pop':         ['calm', 'sad', 'neutral'],
    'Shoegaze':          ['sad', 'calm', 'neutral', 'tired'],

    # World / Reggae
    'Reggae':            ['calm', 'happy', 'neutral'],
    'Dub':               ['calm', 'neutral', 'tired'],
    'World Music':       ['neutral', 'happy', 'calm'],
    'Latin':             ['happy', 'energized', 'neutral'],
    'Afrobeat':          ['happy', 'energized', 'calm'],
    'Bossa Nova':        ['calm', 'happy', 'neutral'],

    # Misc
    'Spoken Word':       ['neutral', 'focused', 'calm'],
    'Soundtrack':        ['neutral', 'calm', 'sad', 'happy'],
    'Stage & Screen':    ['happy', 'sad', 'neutral'],
    'Children\'s':       ['happy', 'neutral'],
    'Holiday':           ['happy', 'calm', 'neutral'],
}

# Weather → moods they complement
WEATHER_MOOD_MAP = {
    'rainy':  ['calm', 'sad', 'focused', 'neutral'],
    'sunny':  ['happy', 'energized', 'neutral'],
    'cloudy': ['neutral', 'tired', 'calm'],
    'cold':   ['calm', 'focused', 'tired'],
    'warm':   ['happy', 'energized'],
    'stormy': ['anxious', 'stressed', 'energized'],
    'snowy':  ['calm', 'happy', 'focused'],
}

# Time of day → moods that naturally fit
TIME_MOOD_MAP = {
    'early_morning': ['calm', 'focused', 'tired'],        # 5–8
    'morning':       ['happy', 'energized', 'focused'],   # 8–12
    'afternoon':     ['neutral', 'happy', 'energized'],   # 12–17
    'evening':       ['calm', 'neutral', 'happy', 'sad'], # 17–21
    'night':         ['calm', 'sad', 'tired', 'neutral'], # 21–24
    'late_night':    ['tired', 'calm', 'sad'],             # 0–5
}

# Day type → moods that naturally fit
DAY_MOOD_MAP = {
    'weekday': ['focused', 'neutral', 'stressed', 'energized'],
    'weekend': ['happy', 'calm', 'neutral', 'energized'],
}

# Season → moods that naturally fit
SEASON_MOOD_MAP = {
    'spring': ['happy', 'energized', 'calm', 'neutral'],
    'summer': ['happy', 'energized', 'neutral'],
    'fall':   ['sad', 'calm', 'neutral', 'focused'],
    'winter': ['calm', 'sad', 'tired', 'focused'],
}


def get_season(month):
    if month in (12, 1, 2): return 'winter'
    if month in (3, 4, 5):  return 'spring'
    if month in (6, 7, 8):  return 'summer'
    return 'fall'


def get_time_of_day(hour):
    if 5  <= hour < 8:  return 'early_morning'
    if 8  <= hour < 12: return 'morning'
    if 12 <= hour < 17: return 'afternoon'
    if 17 <= hour < 21: return 'evening'
    if 21 <= hour < 24: return 'night'
    return 'late_night'


def recency_penalty(last_listened_at, now):
    if last_listened_at is None:
        return 0.0
    try:
        if now.tzinfo is not None and last_listened_at.tzinfo is None:
            from django.utils import timezone
            last_listened_at = timezone.make_aware(last_listened_at)
        days_ago = (now - last_listened_at).days
    except Exception:
        return 0.0
    if days_ago < 1:  return 8.0
    if days_ago < 7:  return 4.0
    if days_ago < 30: return 2.0
    if days_ago < 90: return 1.0
    return 0.0


def score_candidate(candidate, mood, weather, hour, is_weekend, season):
    """
    Score a single album dict against the current context.
    candidate = {discogs_id, title, artist, cover_url, genres, styles}
    Returns 0.0 if no genre matches the mood (album excluded).
    """
    tags = (candidate.get('genres') or []) + (candidate.get('styles') or [])
    time_of_day = get_time_of_day(hour)
    day_type    = 'weekend' if is_weekend else 'weekday'
    s = 0.0

    # 1. Genre-mood match — gate signal
    for tag in tags:
        compatible = GENRE_MOOD_MAP.get(tag, [])
        if mood in compatible:
            position_bonus = 1.0 - (compatible.index(mood) * 0.1)
            s += 10.0 * position_bonus
            break  # best-matching genre only

    # If no genre matched AND the album has genre data, exclude it
    # If the album has NO genre data at all, give a small neutral score
    # so it still shows up as a fallback rather than being invisible
    if s == 0.0:
        if tags:
            return 0.0   # has genres but none matched — skip
        else:
            s = 1.0      # no genre metadata — include weakly as fallback

    # 2. Weather match
    if weather and weather in WEATHER_MOOD_MAP:
        if mood in WEATHER_MOOD_MAP[weather]:
            s += 3.0

    # 3. Time of day
    if mood in TIME_MOOD_MAP.get(time_of_day, []):
        s += 2.0

    # 4. Day type
    if mood in DAY_MOOD_MAP.get(day_type, []):
        s += 1.5

    # 5. Season
    if mood in SEASON_MOOD_MAP.get(season, []):
        s += 1.5

    return s


def recommend_album(user, mood, weather=None, collection=None, now=None):
    """
    Returns a recommendation dict (not a model instance) or None.

    collection: list of dicts passed directly from the frontend —
        [{discogs_id, title, artist, cover_url, genres, styles}, ...]

    Scoring priority:
      1. Behavioural: albums the user has listened to in this mood (DB sessions)
      2. Cold-start:  genre + contextual scoring across the full collection
      3. Absolute fallback: random album from collection if nothing scores
    """
    from .models import ListeningSession

    if not collection:
        return None

    if now is None:
        from django.utils import timezone
        now = timezone.now()

    hour       = now.hour
    dow        = now.weekday()
    month      = now.month
    season     = get_season(month)
    is_weekend = dow >= 5

    # Index collection by discogs_id for quick lookup
    coll_by_id = {c['discogs_id']: c for c in collection}

    # Build last-listened map from DB sessions
    db_sessions = ListeningSession.objects.select_related('album')
    if user is not None:
        db_sessions = db_sessions.filter(user=user)

    last_listened = {}
    for s in db_sessions:
        did = s.album.discogs_id
        if did not in last_listened or s.timestamp > last_listened[did]:
            last_listened[did] = s.timestamp

    # ------------------------------------------------------------------ #
    # PATH A: Behavioural — mood-matched DB sessions                      #
    # ------------------------------------------------------------------ #
    mood_sessions = db_sessions.filter(pre_emotion=mood)

    if mood_sessions.exists():
        scores = defaultdict(float)

        for session in mood_sessions:
            did = session.album.discogs_id
            if did not in coll_by_id:
                continue  # album no longer in collection

            candidate = coll_by_id[did]
            s = 10.0

            if weather and weather in WEATHER_MOOD_MAP:
                if mood in WEATHER_MOOD_MAP[weather]:
                    s += 2.0

            hour_diff = abs(session.hour_of_day - hour)
            hour_diff = min(hour_diff, 24 - hour_diff)
            if hour_diff <= 6:
                s += 1.5 * (1 - hour_diff / 6)

            if (session.day_of_week >= 5) == is_weekend:
                s += 1.0

            if get_season(session.month) == season:
                s += 1.5

            s -= recency_penalty(last_listened.get(did), now)
            scores[did] += s

        if scores:
            best_id = max(scores, key=lambda k: scores[k])
            c = coll_by_id[best_id]
            return {
                'discogs_id': c['discogs_id'],
                'title':      c['title'],
                'artist':     c['artist'],
                'cover_url':  c['cover_url'],
            }

    # ------------------------------------------------------------------ #
    # PATH B: Cold-start — score every album in the collection            #
    # ------------------------------------------------------------------ #
    scores = {}

    for candidate in collection:
        s = score_candidate(candidate, mood, weather, hour, is_weekend, season)
        if s > 0:
            s -= recency_penalty(last_listened.get(candidate['discogs_id']), now)
            scores[candidate['discogs_id']] = s

    if scores:
        best_id = max(scores, key=lambda k: scores[k])
        c = coll_by_id[best_id]
        return {
            'discogs_id': c['discogs_id'],
            'title':      c['title'],
            'artist':     c['artist'],
            'cover_url':  c['cover_url'],
        }

    # ------------------------------------------------------------------ #
    # PATH C: Absolute fallback — nothing scored, return any album        #
    # ------------------------------------------------------------------ #
    import random
    c = random.choice(collection)
    return {
        'discogs_id': c['discogs_id'],
        'title':      c['title'],
        'artist':     c['artist'],
        'cover_url':  c['cover_url'],
    }