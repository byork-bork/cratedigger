# api/models.py
from django.db import models
from django.contrib.auth.models import User

EMOTION_CHOICES = [
    ('stressed', 'Stressed'),
    ('happy', 'Happy'),
    ('tired', 'Tired'),
    ('neutral', 'Neutral'),
    ('calm', 'Calm'),
    ('sad', 'Sad'),
]

class UserProfile(models.Model):
    """
    Extends Django's built-in User to store the Discogs username.
    Created automatically on first login.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    discogs_username = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Profile for {self.discogs_username}"


class Album(models.Model):
    discogs_id = models.IntegerField(unique=True)
    title = models.CharField(max_length=255)
    artist = models.CharField(max_length=255)
    cover_url = models.URLField(blank=True, null=True)
    genres = models.JSONField(default=list, blank=True)
    styles = models.JSONField(default=list, blank=True)
    year = models.IntegerField(null=True, blank=True)
    tracklist = models.JSONField(default=list, blank=True)

    def dominant_mood(self):
        top = self.mood_tags.order_by('-count').first()
        return top.emotion if top else None

    def __str__(self):
        return f"{self.title} by {self.artist}"


class CollectionEntry(models.Model):
    """
    Join table linking a User to an Album they own.
    Created/refreshed at login so the server always has a current picture
    of each user's collection without relying on the frontend to send it.
    """
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='collection')
    album      = models.ForeignKey('Album', on_delete=models.CASCADE, related_name='owners')
    date_added = models.DateTimeField(null=True, blank=True)  # from Discogs date_added field

    class Meta:
        unique_together = ('user', 'album')

    def __str__(self):
        return f"{self.user.username} owns {self.album.title}"


class MoodTag(models.Model):
    album = models.ForeignKey(Album, on_delete=models.CASCADE, related_name='mood_tags')
    emotion = models.CharField(max_length=100, choices=EMOTION_CHOICES)
    count = models.IntegerField(default=1)

    class Meta:
        unique_together = ('album', 'emotion')

    def __str__(self):
        return f"{self.album.title} — {self.emotion} x{self.count}"


class ListeningSession(models.Model):
    user            = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    album           = models.ForeignKey(Album, on_delete=models.CASCADE)
    timestamp       = models.DateTimeField(auto_now_add=True)
    
    pre_emotion     = models.CharField(max_length=100, choices=EMOTION_CHOICES)
    post_emotion    = models.CharField(max_length=100, choices=EMOTION_CHOICES)
    
    side_a_duration = models.IntegerField(default=0)
    side_b_duration = models.IntegerField(default=0)
    
    day_of_week     = models.IntegerField()
    hour_of_day     = models.IntegerField()
    month           = models.IntegerField(default=1)
    weather         = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"{self.album.title} - {self.pre_emotion} -> {self.post_emotion}"

    def total_duration(self):
        return self.side_a_duration + self.side_b_duration