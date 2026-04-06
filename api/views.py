# api/views.py
import os
import requests
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import Album, ListeningSession, MoodTag
from .serializers import ListeningSessionSerializer
from .recommender import recommend_album
from dotenv import load_dotenv

load_dotenv()
DISCOGS_TOKEN = os.getenv('DISCOGS_TOKEN')

DISCOGS_HEADERS = {
    'Authorization': f'Discogs token={DISCOGS_TOKEN}',
    'User-Agent': 'CrateDiggerApp/1.0'
}

@api_view(['GET'])
def get_collection(request, username):
    """Proxies the request to Discogs"""
    sort = request.GET.get('sort', 'added')

    url = f"https://api.discogs.com/users/{username}/collection/folders/0/releases"

    all_releases = []
    page = 1

    try:
        while True:
            params = {
                'page': page,
                'per_page': 100,
                'sort': sort,
                'sort_order': 'desc'
            }
            response = requests.get(url, headers=DISCOGS_HEADERS, params=params)
            response.raise_for_status()
            data = response.json()
            
            all_releases.extend(data.get('releases', []))
            
            pagination = data.get('pagination', {})
            if page >= pagination.get('pages', 1):
                break

            page += 1
            
        return Response({'releases': all_releases})
    
    except requests.exceptions.RequestException as e:
        return Response({'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_release_details(request, release_id):
    """
    Fetches full release details from Discogs for a single album:
    genres, styles, tracklist, year, labels, etc.
    Called when the user clicks on a card (openModal).
    Results are cached in the DB after the first fetch.
    """
    # Check if we already have rich data cached for this release
    try:
        album = Album.objects.get(discogs_id=release_id)
        if album.genres or album.styles or album.tracklist:
            return Response({
                'genres':    album.genres,
                'styles':    album.styles,
                'tracklist': album.tracklist,
                'year':      album.year,
            })
    except Album.DoesNotExist:
        pass  # Not saved yet — that's fine, we'll fetch and cache below

    # Fetch from Discogs
    try:
        url = f"https://api.discogs.com/releases/{release_id}"
        response = requests.get(url, headers=DISCOGS_HEADERS)
        response.raise_for_status()
        data = response.json()

        genres    = data.get('genres', [])
        styles    = data.get('styles', [])
        year      = data.get('year')
        tracklist = [
            {
                'position': track.get('position', ''),
                'title':    track.get('title', ''),
                'duration': track.get('duration', ''),
            }
            for track in data.get('tracklist', [])
            if track.get('type_') != 'heading'   # skip section headers
        ]

        # Cache the details if the album already exists in our DB
        Album.objects.filter(discogs_id=release_id).update(
            genres=genres,
            styles=styles,
            year=year,
            tracklist=tracklist,
        )

        return Response({
            'genres':    genres,
            'styles':    styles,
            'tracklist': tracklist,
            'year':      year,
        })

    except requests.exceptions.RequestException as e:
        return Response({'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def log_session(request):
    """
    Logs a listening session. Creates the Album row if it doesn't exist yet.
    ListeningSession.save() handles auto-assigning mood_tag and
    incrementing the MoodTag tally.
    """
    data = request.data
    
    album, created = Album.objects.get_or_create(
        discogs_id=data['album_id'],
        defaults={
            'title': data['title'],
            'artist': data['artist'],
            'cover_url': data['cover_url'],
        }
    )

    now = timezone.now()
    
    session = ListeningSession.objects.create(
        album=album,
        pre_emotion=data['pre_emotion'],
        post_emotion=data['post_emotion'],
        side_a_duration=data['side_a_duration'],
        side_b_duration=data['side_b_duration'],
        day_of_week=now.weekday(),
        hour_of_day=now.hour,
        month=now.month,
    )
    
    mood_tag, created = MoodTag.objects.get_or_create(
        album=album,
        emotion=data['pre_emotion'],
        defaults={'count': 1}
    )
    if not created:
        mood_tag.count += 1
        mood_tag.save()
    
    return Response(ListeningSessionSerializer(session).data, status=status.HTTP_201_CREATED)

@api_view(['GET'])
def get_recommendation(request):
    """
    Returns a recommended album based on mood and optional context.
    
    Query params:
        mood    (required) — e.g. 'calm', 'happy'
        weather (optional) — e.g. 'rainy', 'sunny'
    """
    mood    = request.GET.get('mood')
    weather = request.GET.get('weather')

    if not mood:
        return Response({'error': 'mood parameter is required'}, status=status.HTTP_400_BAD_REQUEST)

    user  = request.user if request.user.is_authenticated else None
    album = recommend_album(user=user, mood=mood, weather=weather, now=timezone.now())

    if not album:
        return Response({
            'recommendation': None,
            'message': 'Not enough listening history yet.'
        })

    return Response({
        'recommendation': {
            'id':        album.discogs_id,
            'title':     album.title,
            'artist':    album.artist,
            'cover_url': album.cover_url,
            'mood_tag':  album.dominant_mood(),
        }
    })


@api_view(['GET'])
def get_mood_tags(request):
    """
    Returns all MoodTag tallies for a given album.
    Useful for displaying mood badge(s) on a card.

    Query params:
        discogs_id (required)
    """
    discogs_id = request.GET.get('discogs_id')

    if not discogs_id:
        return Response({'error': 'discogs_id parameter is required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        album = Album.objects.get(discogs_id=discogs_id)
    except Album.DoesNotExist:
        return Response({'mood_tags': []})

    tags = MoodTag.objects.filter(album=album).order_by('-count')
    return Response({
        'mood_tags': [
            {'emotion': t.emotion, 'count': t.count}
            for t in tags
        ]
    })