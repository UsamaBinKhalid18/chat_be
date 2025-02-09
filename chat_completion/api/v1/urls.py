

from django.urls import path
from chat_completion.api.v1.views import ChatCompletionView


urlpatterns = [
    path('', ChatCompletionView.as_view(), name='chat'),
]
