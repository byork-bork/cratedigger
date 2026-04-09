# api/views.py
import os
import requests
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.models import User
from .models import Album, ListeningSession, MoodTag, UserProfile
from .serializers import ListeningSessionSerializer
from .recommender import recommend_album
from dotenv import load_dotenv

load_dotenv()
DISCOGS_TOKEN = os.getenv('DISCOGS_TOKEN')

DISCOGS_HEADERS = {
    'Authorization': f'Discogs token={DISCOGS_TOKEN}',
    'User-Agent': 'CrateDiggerApp/1.0'
}


@api_view(['POST'])
def login_user(request):
    """
    Looks up or creates a user by their Discogs username, and fetches their collection.
    
    Request body:
        { "discogs_username": "vinyl_nerd_42" }

    Returns:
        { 
            "user": { "id": 1, ... },
            "releases": [ ... ] 
        }
    """
    discogs_username = request.data.get('discogs_username', '').strip()
    
    # You can still allow sorting to be passed via the request if needed
    sort = request.GET.get('sort', 'added')

    if not discogs_username:
        return Response(
            {'error': 'discogs_username is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    all_releases = []
    page = 1
    url = f"https://api.discogs.com/users/{discogs_username}/collection/folders/0/releases"

    # 1. Fetch the collection (which also validates the username)
    try:
        while True:
            params = {
                'page': page,
                'per_page': 100,
                'sort': sort,
                'sort_order': 'desc'
            }
            response = requests.get(url, headers=DISCOGS_HEADERS, params=params, timeout=30)
            
            # If the user doesn't exist, Discogs returns a 404 on the collection endpoint
            if response.status_code == 404:
                return Response(
                    {'error': f'Username "{discogs_username}" not found on Discogs.'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            response.raise_for_status()
            data = response.json()
            
            all_releases.extend(data.get('releases', []))
            
            pagination = data.get('pagination', {})
            if page >= pagination.get('pages', 1):
                break

            page += 1

    except requests.exceptions.RequestException as e:
        return Response(
            {'error': f'Could not fetch collection or verify username: {str(e)}'},
            status=status.HTTP_502_BAD_GATEWAY
        )

    # 2. If we made it here, the user is valid. Get or create Django models.
    user, user_created = User.objects.get_or_create(
        username=discogs_username,
        defaults={'email': ''}
    )

    profile, _ = UserProfile.objects.get_or_create(
        user=user,
        defaults={'discogs_username': discogs_username}
    )

    # 3. Return both the user context and the collection data
    return Response({
        'user': {
            'id': user.id,
            'username': user.username,
            'discogs_username': profile.discogs_username,
            'created': user_created,
        },
        'releases': all_releases
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
def get_release_details(request, release_id):
    """
    Fetches full release details from Discogs for a single album.
    Results are cached in the DB after the first fetch.
    """
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
        pass

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
            if track.get('type_') != 'heading'
        ]

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
    Accepts an optional user_id to link the session to a user.
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

    # Resolve user from user_id if provided
    user = None
    user_id = data.get('user_id')
    if user_id:
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            pass

    now = timezone.now()
    
    session = ListeningSession.objects.create(
        album           = album,
        user            = user,
        pre_emotion     = data['pre_emotion'],
        post_emotion    = data['post_emotion'],
        side_a_duration = data['side_a_duration'],
        side_b_duration = data['side_b_duration'],
        day_of_week     = now.weekday(),
        hour_of_day     = now.hour,
        month           = now.month,
        weather         = data.get('weather'),
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


@api_view(['POST'])
def get_recommendation(request):
    """
    Returns a recommended album based on mood and optional context.

    Query params:
        mood    (required)
        weather (optional)
    """
    data       = request.data
    mood    = request.GET.get('mood')
    weather = request.GET.get('weather')
    user_id = request.GET.get('user_id')
    collection = data.get('collection', [])  # list of {discogs_id, title, artist, cover_url, genres, styles}

    if not mood:
        return Response({'error': 'mood parameter is required'}, status=status.HTTP_400_BAD_REQUEST)

    if not collection:
        return Response({'recommendation': None, 'message': 'No collection provided.'})

    user = None
    if user_id:
        try:
            from django.contrib.auth.models import User
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            pass

    result = recommend_album(
        user=user,
        mood=mood,
        weather=weather,
        collection=collection,
        now=timezone.now(),
    )

    if not result:
        return Response({'recommendation': None, 'message': 'No matching records found.'})

    return Response({'recommendation': result})


@api_view(['GET'])
def get_mood_tags(request):
    """
    Returns all MoodTag tallies for a given album.

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