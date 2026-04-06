# api/serializers.py
from rest_framework import serializers
from .models import Album, ListeningSession

class AlbumSerializer(serializers.ModelSerializer):
    class Meta:
        model = Album
        fields = '__all__'

class ListeningSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ListeningSession
        fields = '__all__'