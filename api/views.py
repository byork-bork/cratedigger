# api/views.py
import os
import requests
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.models import User
from .models import Album, CollectionEntry, ListeningSession, MoodTag, UserProfile
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
    discogs_username = request.data.get('discogs_username', '').strip()
    sort = request.GET.get('sort', 'added')

    if not discogs_username:
        return Response(
            {'error': 'discogs_username is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    all_releases = []
    page = 1
    url = f"https://api.discogs.com/users/{discogs_username}/collection/folders/0/releases"

    try:
        while True:
            params = {'page': page, 'per_page': 100, 'sort': sort, 'sort_order': 'desc'}
            response = requests.get(url, headers=DISCOGS_HEADERS, params=params, timeout=30)

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

    user, user_created = User.objects.get_or_create(
        username=discogs_username,
        defaults={'email': ''}
    )
    UserProfile.objects.get_or_create(
        user=user,
        defaults={'discogs_username': discogs_username}
    )

    # Upsert every album and collection membership into the DB at login.
    # The collection endpoint already returns genres/styles for most releases,
    # so cold-start recommendations work immediately without extra API calls.
    for item in all_releases:
        info = item.get('basic_information', {})
        discogs_id = info.get('id')
        if not discogs_id:
            continue

        genre_defaults = {}
        genres = info.get('genres') or []
        styles = info.get('styles') or []
        if genres:
            genre_defaults['genres'] = genres
        if styles:
            genre_defaults['styles'] = styles

        artists = info.get('artists', [])
        primary_artist = ''
        if artists:
            primary_artist = artists[0].get('name', '').rstrip(' ,&').strip()

        album, _ = Album.objects.update_or_create(
            discogs_id=discogs_id,
            defaults={
                'title':     info.get('title', ''),
                'artist':    primary_artist,
                'cover_url': info.get('cover_image') or info.get('thumb') or '',
                **genre_defaults,
            }
        )

        CollectionEntry.objects.update_or_create(
            user=user,
            album=album,
            defaults={
                'date_added': parse_datetime(item.get('date_added', '')) or None,
            }
        )

    # Remove stale entries for albums the user no longer owns
    current_ids = {
        item['basic_information']['id']
        for item in all_releases
        if item.get('basic_information', {}).get('id')
    }
    CollectionEntry.objects.filter(user=user).exclude(
        album__discogs_id__in=current_ids
    ).delete()

    return Response({
        'user': {
            'id':               user.id,
            'username':         user.username,
            'discogs_username': discogs_username,
            'created':          user_created,
        },
        'releases': all_releases
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
def get_release_details(request, release_id):
    try:
        album = Album.objects.get(discogs_id=release_id)
        # Only treat the row as fully cached when it has the richer fields
        # (tracklist and year) that the collection endpoint never returns.
        # genres/styles alone means the row was created at login but the
        # detail fetch hasn't happened yet for this album.
        if album.tracklist and album.year is not None:
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

        Album.objects.update_or_create(
            discogs_id=release_id,
            defaults={
                'genres':    genres,
                'styles':    styles,
                'year':      year,
                'tracklist': tracklist,
            }
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
    data = request.data

    album, _ = Album.objects.get_or_create(
        discogs_id=data['album_id'],
        defaults={
            'title':     data['title'],
            'artist':    data['artist'],
            'cover_url': data['cover_url'],
        }
    )

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
    mood and weather are read from the POST body — fixing the original bug
    where they were incorrectly read from query params.

    Collection snapshot from the frontend is still accepted to avoid a
    DB round-trip. If absent, it is built from CollectionEntry.
    """
    data       = request.data
    mood       = data.get('mood')
    weather    = data.get('weather')
    user_id    = data.get('user_id')
    collection = data.get('collection', [])

    if not mood:
        return Response({'error': 'mood is required'}, status=status.HTTP_400_BAD_REQUEST)

    user = None
    if user_id:
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            pass

    # Fallback: build collection from DB if the frontend didn't send it
    if not collection and user:
        entries = CollectionEntry.objects.filter(user=user).select_related('album')
        collection = [
            {
                'discogs_id': e.album.discogs_id,
                'title':      e.album.title,
                'artist':     e.album.artist,
                'cover_url':  e.album.cover_url,
                'genres':     e.album.genres or [],
                'styles':     e.album.styles or [],
            }
            for e in entries
        ]

    if not collection:
        return Response({'recommendation': None, 'message': 'No collection found.'})

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
    discogs_id = request.GET.get('discogs_id')

    if not discogs_id:
        return Response(
            {'error': 'discogs_id parameter is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

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