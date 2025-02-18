

from django.urls import path
from chat_completion.api.v1.views import ChatCompletionView, FileUploadView


urlpatterns = [
    path('', ChatCompletionView.as_view(), name='chat'),
    path('upload/', FileUploadView.as_view(), name='upload'),
]
