# api/recommender.py
import os
from dotenv import load_dotenv
import json
import requests
from collections import defaultdict
from datetime import datetime

# Path to your project root .env
# This goes up one level from 'api/recommender.py' to find the .env file
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path)

# ---------------------------------------------------------------------------
# Genre → compatible moods
# ---------------------------------------------------------------------------
GENRE_MOOD_MAP = {
    # Rock family
    'Rock':              ['stressed', 'happy', 'neutral'],
    'Hard Rock':         ['stressed'],
    'Punk':              ['stressed'],
    'Alternative Rock':  ['neutral', 'sad', 'stressed', 'calm'],
    'Indie Rock':        ['neutral', 'calm', 'happy', 'sad'],
    'Psychedelic Rock':  ['calm', 'neutral', 'happy'],
    'Progressive Rock':  ['neutral', 'calm'],
    'Folk Rock':         ['calm', 'sad', 'neutral', 'happy'],
    'Classic Rock':      ['happy', 'neutral'],

    # Electronic
    'Electronic':        ['neutral'],
    'Ambient':           ['calm', 'tired', 'stressed'],
    'Techno':            ['stressed'],
    'House':             ['happy', 'neutral'],
    'Drum n Bass':       ['happy', 'stressed'],
    'IDM':               ['neutral', 'calm'],
    'Downtempo':         ['calm', 'tired', 'neutral', 'sad'],
    'Trip Hop':          ['sad', 'calm', 'neutral', 'tired'],

    # Jazz
    'Jazz':              ['calm', 'neutral', 'happy'],
    'Bebop':             ['neutral'],
    'Hard Bop':          ['happy'],
    'Cool Jazz':         ['calm', 'neutral'],
    'Free Jazz':         ['stressed'],
    'Fusion':            ['happy'],
    'Smooth Jazz':       ['calm', 'happy', 'neutral'],
    'Soul Jazz':         ['happy', 'calm', 'neutral'],
    'Modal Jazz':        ['calm', 'neutral'],

    # Classical
    'Classical':         ['calm', 'sad', 'neutral'],
    'Baroque':           ['calm', 'neutral'],
    'Romantic':          ['sad', 'calm', 'happy', 'neutral'],
    'Contemporary':      ['neutral'],
    'Opera':             ['sad', 'happy'],
    'Chamber Music':     ['calm', 'neutral'],

    # Soul / R&B / Funk
    'Soul':              ['happy', 'sad', 'calm', 'neutral'],
    'R&B':               ['happy', 'calm', 'sad', 'neutral'],
    'Funk':              ['happy', 'neutral'],
    'Disco':             ['happy', 'neutral'],
    'Neo Soul':          ['calm', 'sad', 'neutral', 'happy'],

    # Hip Hop
    'Hip Hop':           ['happy', 'neutral', 'stressed'],
    'Rap':               ['stressed', 'neutral'],
    'Lo-fi':             ['calm', 'tired', 'neutral'],

    # Folk / Country / Americana
    'Folk':              ['calm', 'sad', 'happy', 'neutral'],
    'Country':           ['happy', 'sad', 'calm', 'neutral'],
    'Americana':         ['calm', 'sad', 'neutral'],
    'Bluegrass':         ['happy', 'calm'],
    'Blues':             ['sad', 'calm', 'neutral'],

    # Metal
    'Metal':             ['stressed'],
    'Heavy Metal':       ['stressed'],
    'Death Metal':       ['stressed'],
    'Black Metal':       ['stressed', 'sad'],
    'Doom Metal':        ['sad', 'tired', 'stressed'],
    'Post-Metal':        ['sad', 'neutral', 'stressed'],

    # Pop
    'Pop':               ['happy', 'neutral'],
    'Synth-pop':         ['happy', 'neutral'],
    'Dream Pop':         ['calm', 'sad', 'neutral'],
    'Shoegaze':          ['sad', 'calm', 'neutral', 'tired'],

    # World / Reggae
    'Reggae':            ['calm', 'happy', 'neutral'],
    'Dub':               ['calm', 'neutral', 'tired'],
    'World Music':       ['neutral', 'happy', 'calm'],
    'Latin':             ['happy', 'neutral'],
    'Afrobeat':          ['happy', 'calm'],
    'Bossa Nova':        ['calm', 'happy', 'neutral'],

    # Misc
    'Spoken Word':       ['neutral', 'calm'],
    'Soundtrack':        ['neutral', 'calm', 'sad', 'happy'],
    'Stage & Screen':    ['happy', 'sad', 'neutral'],
    "Children's":        ['happy', 'neutral'],
    'Holiday':           ['happy', 'calm', 'neutral'],
}

# Moods that are "negative" and where a listener likely wants to shift away
# (used when we have no personal history to infer intent from)
DEFAULT_ESCAPE_MOODS = {'stressed', 'sad', 'tired'}

# For each "escape" mood, what moods does a listener typically want to reach?
DEFAULT_TARGET_MOOD = {
    'stressed': 'calm',
    'sad':      'happy',
    'tired':    'happy',
}

# Weather → moods they complement
# Used for context signals in Path A (behavioural) scoring.
WEATHER_MOOD_MAP = {
    'rainy':  ['calm', 'sad', 'neutral'],
    'clear':  ['happy', 'neutral'],
    'cloudy': ['neutral', 'tired', 'calm'],
    'cold':   ['calm', 'tired'],
    'warm':   ['happy'],
    'stormy': ['stressed', 'calm'],
    'snowy':  ['calm', 'happy'],
}

# Weather → genres/styles that suit it well.
# These are used as direct per-album score modifiers in score_candidate so
# that weather can discriminate between albums that score equally on mood.
# Positive values boost an album; negative values penalise it.
WEATHER_GENRE_AFFINITY = {
    'rainy': {
        # Good fits
        'Folk':             2.5, 'Ambient':         2.5, 'Trip Hop':        2.5,
        'Shoegaze':         2.0, 'Post-Metal':       2.0, 'Dream Pop':       2.0,
        'Jazz':             2.0, 'Cool Jazz':        2.0, 'Blues':           2.0,
        'Classical':        1.5, 'Downtempo':        1.5, 'Neo Soul':        1.5,
        'Indie Rock':       1.5, 'Alternative Rock': 1.5, 'Bossa Nova':      1.5,
        # Poor fits
        'Disco':           -2.0, 'Funk':            -2.0, 'Latin':          -2.0,
        'Punk':            -1.5, 'Hard Rock':       -1.5, 'Drum n Bass':    -1.5,
    },
    'clear': {
        'Pop':              2.5, 'Disco':            2.5, 'Funk':            2.5,
        'Afrobeat':         2.5, 'Latin':            2.0, 'Reggae':          2.0,
        'Soul':             2.0, 'Classic Rock':     1.5, 'Bluegrass':       1.5,
        'Country':          1.5, 'Folk Rock':        1.5, 'Bossa Nova':      2.0,
        # Poor fits
        'Doom Metal':      -2.0, 'Black Metal':     -2.0, 'Ambient':        -1.5,
        'Shoegaze':        -1.5, 'Trip Hop':        -1.5,
    },
    'cloudy': {
        'Indie Rock':       2.0, 'Alternative Rock': 2.0, 'Downtempo':       2.0,
        'Dream Pop':        2.0, 'Shoegaze':         2.0, 'Folk':            1.5,
        'Post-Metal':       1.5, 'IDM':              1.5, 'Classical':       1.5,
        'Jazz':             1.5, 'Soul':             1.5,
        # Poor fits
        'Disco':           -1.5, 'Latin':           -1.5, 'Afrobeat':       -1.5,
    },
    'cold': {
        'Classical':        2.5, 'Ambient':          2.5, 'Folk':            2.0,
        'Jazz':             2.0, 'Blues':            2.0, 'Doom Metal':      2.0,
        'Chamber Music':    2.0, 'Baroque':          1.5, 'IDM':             1.5,
        'Shoegaze':         1.5, 'Dream Pop':        1.5, 'Country':         1.5,
        # Poor fits
        'Reggae':          -2.0, 'Afrobeat':        -2.0, 'Latin':          -1.5,
        'Disco':           -1.5,
    },
    'warm': {
        'Reggae':           2.5, 'Afrobeat':         2.5, 'Bossa Nova':      2.5,
        'Latin':            2.5, 'Funk':             2.0, 'Soul':            2.0,
        'Disco':            2.0, 'Pop':              1.5, 'R&B':             1.5,
        'Folk Rock':        1.5, 'Classic Rock':     1.5,
        # Poor fits
        'Black Metal':     -2.0, 'Doom Metal':      -2.0, 'Ambient':        -1.0,
    },
    'stormy': {
        'Metal':            2.5, 'Heavy Metal':      2.5, 'Post-Metal':      2.5,
        'Punk':             2.0, 'Hard Rock':        2.0, 'Free Jazz':       2.0,
        'Doom Metal':       2.0, 'Black Metal':      2.0, 'Drum n Bass':     1.5,
        'Techno':           1.5, 'Electronic':       1.5, 'Progressive Rock': 1.5,
        # Poor fits
        'Bossa Nova':      -2.0, 'Smooth Jazz':     -2.0, "Children's":     -2.0,
        'Holiday':         -1.5, 'Folk':            -1.0,
    },
    'snowy': {
        'Classical':        2.5, 'Ambient':          2.5, 'Folk':            2.0,
        'Chamber Music':    2.0, 'Baroque':          2.0, 'Jazz':            2.0,
        'Downtempo':        2.0, 'Dream Pop':        1.5, 'Shoegaze':        1.5,
        'Country':          1.5, 'Blues':            1.5, 'Soul':            1.5,
        # Poor fits
        'Punk':            -1.5, 'Hard Rock':       -1.5, 'Drum n Bass':    -1.5,
        'Afrobeat':        -2.0, 'Latin':           -1.5,
    },
}

# Time of day → moods that naturally fit
TIME_MOOD_MAP = {
    'early_morning': ['calm', 'tired'],
    'morning':       ['happy'],
    'afternoon':     ['neutral', 'happy'],
    'evening':       ['calm', 'neutral', 'happy', 'sad'],
    'night':         ['calm', 'sad', 'tired', 'neutral'],
    'late_night':    ['tired', 'calm', 'sad'],
}

# Day type → moods that naturally fit
DAY_MOOD_MAP = {
    'weekday': ['neutral', 'stressed', 'happy'],
    'weekend': ['happy', 'calm', 'neutral'],
}

# Season → moods that naturally fit
SEASON_MOOD_MAP = {
    'spring': ['happy', 'calm', 'neutral'],
    'summer': ['happy', 'neutral'],
    'fall':   ['sad', 'calm', 'neutral'],
    'winter': ['calm', 'sad', 'tired'],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def recency_penalty(session_count, last_listened_at, now):
    """
    Returns a penalty score for albums that have been played recently or often.

    Two components:
      - Staleness penalty: discourages replaying something listened to very recently.
      - Overplay penalty: discourages albums that dominate the listening history,
        so the recommender surfaces less-explored records.

    Applied ONCE per album after all session scores are accumulated.
    """
    penalty = 0.0

    if last_listened_at is not None:
        try:
            if now.tzinfo is not None and last_listened_at.tzinfo is None:
                from django.utils import timezone
                last_listened_at = timezone.make_aware(last_listened_at)
            days_ago = (now - last_listened_at).days
        except Exception:
            days_ago = 999

        if days_ago < 1:    penalty += 8.0
        elif days_ago < 7:  penalty += 4.0
        elif days_ago < 30: penalty += 2.0
        elif days_ago < 90: penalty += 1.0

    if session_count >= 10:  penalty += 6.0
    elif session_count >= 5: penalty += 3.0
    elif session_count >= 3: penalty += 1.5
    elif session_count >= 2: penalty += 0.5

    return penalty


# ---------------------------------------------------------------------------
# Mood-transformation profile
# ---------------------------------------------------------------------------

def build_transformation_profile(db_sessions):
    """
    Analyses a user's listening history to build a personalised mood-shift map.

    Returns a dict:
        {
          pre_mood: {
            post_mood: {
              'count':   int,          # how many times this shift was observed
              'genres':  {genre: int}  # which genres were associated with it
            }
          }
        }

    This lets us answer questions like:
      "When this user is stressed, they most often end up feeling calm,
       and they tend to get there via Jazz and Ambient records."
    """
    profile = defaultdict(lambda: defaultdict(lambda: {'count': 0, 'genres': defaultdict(int)}))

    for session in db_sessions:
        pre  = session.pre_emotion
        post = session.post_emotion
        if not pre or not post:
            continue

        profile[pre][post]['count'] += 1

        # Credit the album's genres/styles to this transformation
        album = session.album
        for tag in (album.genres or []) + (album.styles or []):
            profile[pre][post]['genres'][tag] += 1

    return profile


def infer_target_mood(pre_mood, transformation_profile):
    """
    Given a user's current mood and their personal history, infer what mood
    they are most likely trying to reach.

    Falls back to generic defaults when there is insufficient history.

    Returns (target_mood, confidence):
      target_mood  — string, the mood to score albums toward
      confidence   — 'personal' | 'default' | 'stay'
    """
    history = transformation_profile.get(pre_mood, {})

    # Filter out "staying in the same mood" — we want intentional shifts
    shifts = {post: data for post, data in history.items() if post != pre_mood}

    if shifts:
        # Pick the most frequently reached post-mood
        best_post = max(shifts, key=lambda p: shifts[p]['count'])
        total = sum(d['count'] for d in history.values())
        same  = history.get(pre_mood, {}).get('count', 0)

        # If they stay in the same mood more than 60% of the time, they likely
        # want to lean in, not escape — score toward the current mood
        if same / max(total, 1) > 0.6:
            return pre_mood, 'stay'

        return best_post, 'personal'

    # No personal data: use defaults for negative moods, otherwise stay
    if pre_mood in DEFAULT_TARGET_MOOD:
        return DEFAULT_TARGET_MOOD[pre_mood], 'default'

    return pre_mood, 'stay'


def genres_for_transformation(pre_mood, target_mood, transformation_profile):
    """
    Returns an ordered list of genres that have been associated with the
    pre→target mood shift for this user, most frequent first.
    """
    data = transformation_profile.get(pre_mood, {}).get(target_mood, {})
    genre_counts = data.get('genres', {})
    return sorted(genre_counts, key=lambda g: genre_counts[g], reverse=True)


# ---------------------------------------------------------------------------
# Candidate scoring
# ---------------------------------------------------------------------------

def score_candidate(candidate, mood, weather, hour, is_weekend, season,
                    target_mood=None, transformation_genres=None, is_unplayed=False):
    """
    Score a single album dict against the current context.

    candidate = {discogs_id, title, artist, cover_url, genres, styles}

    New parameters vs. the original:
      target_mood           — the mood we're trying to help the user reach.
                              If different from `mood`, albums that match the
                              target get a bonus on top of the base score.
      transformation_genres — genres personally associated with the pre→target
                              shift for this user; ranked list, most useful first.

    Returns (score, genre_matched):
      score         — float, 0.0 means excluded
      genre_matched — bool, True if at least one genre tag matched the mood
    """
    tags        = (candidate.get('genres') or []) + (candidate.get('styles') or [])
    time_of_day = get_time_of_day(hour)
    day_type    = 'weekend' if is_weekend else 'weekday'
    s           = 0.0
    genre_matched = False

    # ------------------------------------------------------------------
    # 1. Genre–mood match (primary signal)
    #    Score against both the current mood AND the target mood so that
    #    albums bridging both states rank highest.
    # ------------------------------------------------------------------
    best_genre_score = 0.0
    for tag in tags:
        compatible = GENRE_MOOD_MAP.get(tag, [])

        # Match against current mood
        if mood in compatible:
            pos_bonus      = 1.0 - (compatible.index(mood) * 0.1)
            candidate_score = 10.0 * max(pos_bonus, 0.1)
            if candidate_score > best_genre_score:
                best_genre_score = candidate_score
            genre_matched = True

        # Extra credit for matching the target mood (when different)
        if target_mood and target_mood != mood and target_mood in compatible:
            pos_bonus       = 1.0 - (compatible.index(target_mood) * 0.1)
            target_score    = 5.0 * max(pos_bonus, 0.1)   # half-weight
            if target_score > best_genre_score:
                best_genre_score = target_score
            genre_matched = True

    if best_genre_score > 0:
        s += best_genre_score
    elif tags:
        return 0.0, False   # genres present but none matched — exclude
    else:
        s = 1.0             # no metadata — include weakly

    # ------------------------------------------------------------------
    # 2. Personal transformation-genre bonus
    #    If this album's genres appear in the user's personal "what helps
    #    me shift from X to Y" list, reward them proportionally.
    # ------------------------------------------------------------------
    if transformation_genres:
        for tag in tags:
            if tag in transformation_genres:
                rank  = transformation_genres.index(tag)
                bonus = 3.0 * (1.0 - rank / max(len(transformation_genres), 1))
                s    += max(bonus, 0.5)
                break  # one bonus per album is enough

    # ------------------------------------------------------------------
    # 3. Weather — genre-affinity scoring
    #
    #    WEATHER_GENRE_AFFINITY maps each weather condition directly to
    #    genres that suit (positive) or clash (negative) with it.  This
    #    gives weather real discriminating power: two albums that score
    #    equally on mood can now diverge based on how well their genres
    #    fit the current conditions, rather than receiving a flat bonus
    #    that left their relative ranking unchanged.
    # ------------------------------------------------------------------
    if weather and weather in WEATHER_GENRE_AFFINITY:
        genre_affinities = WEATHER_GENRE_AFFINITY[weather]
        best_weather_bonus = 0.0
        for tag in tags:
            if tag in genre_affinities:
                if abs(genre_affinities[tag]) > abs(best_weather_bonus):
                    best_weather_bonus = genre_affinities[tag]
        s += best_weather_bonus

    # ------------------------------------------------------------------
    # 4. Time of day
    # ------------------------------------------------------------------
    if mood in TIME_MOOD_MAP.get(time_of_day, []):
        s += 2.0

    # ------------------------------------------------------------------
    # 5. Day type
    # ------------------------------------------------------------------
    if mood in DAY_MOOD_MAP.get(day_type, []):
        s += 1.5

    # ------------------------------------------------------------------
    # 6. Season
    # ------------------------------------------------------------------
    if mood in SEASON_MOOD_MAP.get(season, []):
        s += 1.5

    # ------------------------------------------------------------------
    # 7. Album has [not] been played
    # ------------------------------------------------------------------
    if is_unplayed:
        s += 6.0  # enough to compete with played albums, not enough to override mood fit

    return s, genre_matched


# ---------------------------------------------------------------------------
# LLM reasoning layer
# ---------------------------------------------------------------------------

def build_llm_prompt(mood, target_mood, confidence, weather, time_of_day,
                     day_type, season, top_candidates, transformation_profile):
    """
    Builds the prompt sent to Gemini.

    top_candidates — list of dicts:
        {discogs_id, title, artist, genres, styles, score}
        (already sorted best-first, capped at ~5)

    Gemini is asked to:
      1. Re-rank or confirm the top candidate using qualitative reasoning.
      2. Write a short, warm explanation the user will actually see.

    The response is requested as JSON so it's easy to parse.
    """

    # Summarise what we know about the user's personal transformation history
    # for the current mood — feed this to the model as context
    history_summary = ""
    mood_history = transformation_profile.get(mood, {})
    if mood_history:
        parts = []
        for post_mood, data in sorted(mood_history.items(),
                                      key=lambda x: x[1]['count'], reverse=True):
            top_genres = sorted(data['genres'], key=lambda g: data['genres'][g], reverse=True)[:3]
            parts.append(
                f"  • After listening while {mood}, they ended up feeling {post_mood} "
                f"{data['count']} time(s)"
                + (f" — often via {', '.join(top_genres)}" if top_genres else "")
            )
        history_summary = "Personal mood-shift history for this user:\n" + "\n".join(parts)
    else:
        history_summary = "No personal listening history for this mood yet (cold start)."

    # Describe the candidates
    candidates_text = ""
    for i, c in enumerate(top_candidates, 1):
        genres_str = ", ".join((c.get('genres') or []) + (c.get('styles') or [])) or "unknown"
        unplayed_note = " [NOT YET IN YOUR LISTENING HISTORY]" if c.get('is_unplayed') else ""
        candidates_text += (
            f"{i}. \"{c['title']}\" by {c['artist']} "
            f"[score: {c['score']:.1f}] — genres: {genres_str}{unplayed_note}\n"
        )

    shift_note = (
        f"The user currently feels **{mood}**. "
        + (
            f"Based on their history, they likely want to move toward feeling **{target_mood}** "
            f"(confidence: {confidence})."
            if target_mood != mood
            else f"Based on their history, they seem to want to stay in the **{mood}** mood."
        )
    )

    prompt = f"""You are the recommendation engine for CrateDigger, an app for vinyl record collectors.
Your job is to choose the single best album for a listener right now and explain the choice in a warm, 
personal, one-sentence way — the kind of thing a knowledgeable friend who knows their collection would say.

Current context:
- Mood: {mood}
- Time of day: {time_of_day}
- Day type: {day_type}
- Season: {season}
- Weather: {weather or 'not specified'}
- {shift_note}

{history_summary}

Top scored candidates (already filtered and ranked by the algorithmic layer):
{candidates_text}
Your task:
1. Review the candidates. You may re-rank them if you have a good qualitative reason 
   (e.g. a Jazz album on a rainy evening has texture the score missed), but do not 
   override the algorithmic top pick without a clear reason.
2. Write a single warm, specific sentence explaining why this album fits right now.
   Reference the mood, the time/weather/season if relevant, and the album's character.
   Do NOT be generic. Do NOT say "this album matches your mood."
3. If the chosen album is marked [NOT YET IN YOUR LISTENING HISTORY], frame the 
   explanation around discovery — e.g. "this would be a great one to explore" or 
   "you haven't spun this one yet, and tonight feels right for it." Don't use those 
   exact phrases; make it feel natural and specific to the album.

Respond ONLY with valid JSON in exactly this format (no markdown, no extra keys):
{{
  "chosen_index": <1-based integer from the candidate list>,
  "explanation": "<one sentence, warm and specific>"
}}"""

    return prompt


def get_llm_recommendation(prompt):
    """
    Calls the Gemini API and parses the JSON response.

    Returns (chosen_index, explanation) or (None, None) on any failure.
    chosen_index is 1-based.
    """
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        return None, None

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={api_key}"

    try:
        response = requests.post(
            url,
            headers={'Content-Type': 'application/json'},
            json={
                "contents": [{
                    "parts": [{"text": prompt}]
                }],
                "generationConfig": {
                    # Forces the model to return a valid JSON object
                    "responseMimeType": "application/json",
                    "temperature": 0.7
                }
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        # Extract the text part from the Gemini response structure
        raw = data['candidates'][0]['content']['parts'][0]['text'].strip()

        # Because we enforced JSON mime type, we can load it directly
        parsed = json.loads(raw)
        return int(parsed['chosen_index']), parsed.get('explanation', '')

    except Exception as e:
        # Temporarily print the exact error to the terminal
        print(f"DEBUG LLM ERROR: {e}")
        
        # LLM layer is best-effort; fall back silently to algorithmic pick
        return None, None

    #except Exception:
        # LLM layer is best-effort; fall back silently to algorithmic pick
    #    return None, None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def recommend_album(user, mood, weather=None, collection=None, now=None):
    """
    Returns a recommendation dict or None.

    collection: list of dicts from the DB / Discogs proxy —
        [{discogs_id, title, artist, cover_url, genres, styles}, ...]

    The returned dict now includes an optional 'explanation' key when the
    LLM layer is available:
        {discogs_id, title, artist, cover_url, explanation?}

    Scoring strategy
    ────────────────
    STEP 0  Build a personalised mood-transformation profile from the user's
            full listening history (pre_emotion → post_emotion patterns, with
            genres credited to each observed shift).

    STEP 1  Infer the user's likely target mood — do they want to stay in
            their current state, or shift toward something else?  Personal
            history is used first; generic defaults apply on cold start.

    PATH A  Behavioural — the user has prior sessions logged for this mood.
            Each session contributes contextual scores plus the genre-fit
            score of the album, now aware of both the current and target mood.
            A recency+overplay penalty is applied once per album at the end.

    PATH B  Cold-start — no mood-matched history.  Every album is scored on
            genre + context fit alone, with the same recency penalty.

    PATH C  Absolute fallback — nothing scored.  Returns a random album.

    STEP 2  The top ~5 candidates from whichever path ran are passed to an
            LLM (gemini-2.0-flash) for lightweight qualitative reasoning.  The
            model may re-rank within the shortlist and adds a one-sentence
            personalised explanation.  If the API call fails for any reason,
            the system falls back gracefully to the algorithmic top pick
            with no explanation.
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
    time_of_day = get_time_of_day(hour)
    day_type    = 'weekend' if is_weekend else 'weekday'

    coll_by_id = {c['discogs_id']: c for c in collection}

    # ------------------------------------------------------------------
    # STEP 0: Build transformation profile from full history
    # ------------------------------------------------------------------
    db_sessions = ListeningSession.objects.select_related('album')
    if user is not None:
        db_sessions = db_sessions.filter(user=user)

    transformation_profile = build_transformation_profile(db_sessions)

    last_listened  = {}
    session_counts = defaultdict(int)

    for s in db_sessions:
        did = s.album.discogs_id
        session_counts[did] += 1
        if did not in last_listened or s.timestamp > last_listened[did]:
            last_listened[did] = s.timestamp

    # ------------------------------------------------------------------
    # STEP 1: Infer target mood and personal transformation genres
    # ------------------------------------------------------------------
    target_mood, confidence = infer_target_mood(mood, transformation_profile)
    transformation_genres   = genres_for_transformation(mood, target_mood, transformation_profile)

    # ------------------------------------------------------------------
    # PATH A: Behavioural — mood-matched DB sessions
    # ------------------------------------------------------------------
    mood_sessions = db_sessions.filter(pre_emotion=mood)

    if mood_sessions.exists():
        raw_scores = defaultdict(float)

        for session in mood_sessions:
            did = session.album.discogs_id
            if did not in coll_by_id:
                continue

            candidate = coll_by_id[did]
            s = 0.0

            s += 10.0  # base behavioural signal

            genre_score, _ = score_candidate(
                candidate, mood, weather, hour, is_weekend, season,
                target_mood=target_mood,
                transformation_genres=transformation_genres,
            )
            s += genre_score * 0.5

            hour_diff = abs(session.hour_of_day - hour)
            hour_diff = min(hour_diff, 24 - hour_diff)
            if hour_diff <= 6:
                s += 1.5 * (1 - hour_diff / 6)

            if (session.day_of_week >= 5) == is_weekend:
                s += 1.0

            if get_season(session.month) == season:
                s += 1.5

            raw_scores[did] += s

        final_scores = {}
        for did, score in raw_scores.items():
            penalty = recency_penalty(session_counts[did], last_listened.get(did), now)
            final_scores[did] = score - penalty

        # Also score unplayed albums so underexplored records can compete
        for candidate in collection:
            did = candidate['discogs_id']
            if did in final_scores:
                continue
            is_unplayed = did not in session_counts
            genre_score, _ = score_candidate(
                candidate, mood, weather, hour, is_weekend, season,
                target_mood=target_mood,
                transformation_genres=transformation_genres,
                is_unplayed=is_unplayed,
            )
            if genre_score > 0:
                final_scores[did] = genre_score

        if final_scores:
            return _finalise(
                final_scores, coll_by_id, mood, target_mood, confidence,
                weather, time_of_day, day_type, season, transformation_profile, session_counts,
            )

    # ------------------------------------------------------------------
    # PATH B: Cold-start — genre + context scoring only
    # ------------------------------------------------------------------
    scores = {}
    for candidate in collection:
        is_unplayed = did not in session_counts
        did = candidate['discogs_id']
        genre_score, _ = score_candidate(
            candidate, mood, weather, hour, is_weekend, season,
            target_mood=target_mood,
            transformation_genres=transformation_genres,
            is_unplayed=is_unplayed,
        )
        if genre_score > 0:
            penalty = recency_penalty(session_counts[did], last_listened.get(did), now)
            scores[did] = genre_score - penalty

    if scores:
        return _finalise(
            scores, coll_by_id, mood, target_mood, confidence,
            weather, time_of_day, day_type, season, transformation_profile, session_counts,
        )

    # ------------------------------------------------------------------
    # PATH C: Absolute fallback
    # ------------------------------------------------------------------
    import random
    c = random.choice(collection)
    return {
        'discogs_id':  c['discogs_id'],
        'title':       c['title'],
        'artist':      c['artist'],
        'cover_url':   c['cover_url'],
        'explanation': None,
    }


def _finalise(scores, coll_by_id, mood, target_mood, confidence,
              weather, time_of_day, day_type, season, transformation_profile, session_counts,):
    """
    Given a complete scores dict, build a shortlist for the LLM and return
    the final recommendation with an optional explanation.
    """
    # Sort all candidates and take the top 5 for the LLM
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top5   = ranked[:5]

    top_candidates = []
    for did, score in top5:
        c = coll_by_id[did]
        top_candidates.append({
            'discogs_id': did,
            'title':      c['title'],
            'artist':     c['artist'],
            'genres':     c.get('genres') or [],
            'styles':     c.get('styles') or [],
            'score':      score,
            'is_unplayed': did not in session_counts,
        })

    # ------------------------------------------------------------------
    # LLM reasoning pass — best-effort, fails gracefully
    # ------------------------------------------------------------------
    chosen_index = 1          # default: take the algorithmic top pick
    explanation  = None

    prompt = build_llm_prompt(
        mood, target_mood, confidence, weather,
        time_of_day, day_type, season,
        top_candidates, transformation_profile,
    )
    llm_index, llm_explanation = get_llm_recommendation(prompt)

    if llm_index is not None and 1 <= llm_index <= len(top_candidates):
        chosen_index = llm_index
        explanation  = llm_explanation

    chosen = top_candidates[chosen_index - 1]
    c      = coll_by_id[chosen['discogs_id']]

    return {
        'discogs_id':  c['discogs_id'],
        'title':       c['title'],
        'artist':      c['artist'],
        'cover_url':   c['cover_url'],
        'explanation': explanation,   # None if LLM unavailable
    }