import uuid
from django.db import models

from chat_completion.utils import get_upload_path


class FileUpload(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    file = models.FileField(upload_to=get_upload_path)
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=150)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    @property
    def extension(self):
        return self.original_name.split('.')[-1]
