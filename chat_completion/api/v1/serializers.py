from django.conf import settings
from rest_framework import serializers

from chat_completion.models import FileUpload


class FileUploadSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = FileUpload
        fields = ['uuid', 'file', 'original_name', 'uploaded_at', 'url', 'extension', 'content_type']

    def get_url(self, obj):
        return settings.BASE_URL + obj.file.url
