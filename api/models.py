# api/models.py
from django.db import models
from django.contrib.auth.models import User

EMOTION_CHOICES = [
    ('stressed', 'Stressed'),
    ('happy', 'Happy'),
    ('tired', 'Tired'),
    ('anxious', 'Anxious'),
    ('neutral', 'Neutral'),
    ('calm', 'Calm'),
    ('sad', 'Sad'),
]

class Album(models.Model):
    discogs_id = models.IntegerField(unique=True)
    title = models.CharField(max_length=255)
    artist = models.CharField(max_length=255)
    cover_url = models.URLField(blank=True, null=True)
    genres = models.JSONField(default=list, blank=True)   # e.g. ["Rock", "Jazz"]
    styles = models.JSONField(default=list, blank=True)   # e.g. ["Bebop", "Hard Bop"]
    year = models.IntegerField(null=True, blank=True)
    tracklist = models.JSONField(default=list, blank=True)

    def dominant_mood(self):
        top = self.mood_tags.order_by('-count').first()
        return top.emotion if top else None

    def __str__(self):
        return f"{self.title} by {self.artist}"

class MoodTag(models.Model):
    album = models.ForeignKey(Album, on_delete=models.CASCADE, related_name='mood_tags')
    emotion = models.CharField(max_length=100, choices=EMOTION_CHOICES)
    count = models.IntegerField(default=1)  # how many times this mood was logged

    class Meta:
        unique_together = ('album', 'emotion')  # one row per album+emotion pair

    def __str__(self):
        return f"{self.album.title} — {self.emotion} x{self.count}"

class ListeningSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    album = models.ForeignKey(Album, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Updated Emotion Tracking
    pre_emotion = models.CharField(max_length=100, choices=EMOTION_CHOICES)
    post_emotion = models.CharField(max_length=100, choices=EMOTION_CHOICES)
    
    # New Timer Tracking (Stored in seconds)
    side_a_duration = models.IntegerField(default=0)
    side_b_duration = models.IntegerField(default=0)
    
    day_of_week = models.IntegerField()
    hour_of_day = models.IntegerField()
    month = models.IntegerField(default=1)

    def __str__(self):
        return f"{self.album.title} - {self.pre_emotion} -> {self.post_emotion}"

    def total_duration(self):
        return self.side_a_duration + self.side_b_duration