from django.http import StreamingHttpResponse
from rest_framework.views import APIView
from google import genai
from django.conf import settings
from openai import OpenAI
from anthropic import Anthropic
import logging
import sys

from chat_completion.permissions import IsSubscribed


logger = logging.getLogger(__name__)


class ChatCompletionView(APIView):
    http_method_names = ['post']
    permission_classes = [IsSubscribed]

    def post(self, request):
        model = request.data.get('model')
        messages = request.data.get('messages', [])

        if not messages:
            return StreamingHttpResponse("No messages provided.", status=400)

        def client_disconnected():
            return request.META.get("HTTP_CONNECTION") == "close"

        # 🔹 Gemini 1.5 Pro
        if model == 'Gemini 1.5 Pro':
            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            gemini_messages = [
                {"role": 'user' if msg['isUser'] else 'assistant', "parts": [{"text": msg['text']}]}
                for msg in messages[:-1]
            ]
            chat = client.chats.create(history=gemini_messages, model='gemini-2.0-flash')

            def gemini_event_stream():
                try:
                    response = chat.send_message_stream(messages[-1]['text'])
                    for chunk in response:
                        if client_disconnected():
                            logger.info("Client disconnected, stopping Gemini stream.")
                            sys.exit(0)  # Hard stop
                        yield chunk.text
                except Exception as e:
                    logger.error(f"Gemini streaming error: {e}")

            return StreamingHttpResponse(gemini_event_stream(), content_type='text/plain')

        openai_messages = [
            {"role": 'user' if msg['isUser'] else 'assistant', "content": msg['text']}
            for msg in messages
        ]

        if model in ['GPT 4o Mini', 'GPT 4o']:
            client = OpenAI(api_key=settings.OPENAI_API_KEY)

            def openai_event_stream():
                try:
                    response = client.chat.completions.create(
                        model="gpt-4o-mini" if model == "GPT 4o Mini" else "gpt-4o",
                        messages=openai_messages,
                        stream=True
                    )
                    for chunk in response:
                        if client_disconnected():
                            logger.info("Client disconnected, stopping OpenAI stream.")
                            response.close()  # Attempt to stop OpenAI request
                            break
                        yield chunk.choices[0].delta.content or ""
                except Exception as e:
                    logger.error(f"OpenAI streaming error: {e}")

            return StreamingHttpResponse(openai_event_stream(), content_type='text/plain')

        # 🔹 Claude 3.5 Sonnet
        if model == 'Claude 3.5 Sonnet':
            client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)

            def claude_event_stream():
                try:
                    with client.messages.stream(
                        max_tokens=1024,
                        messages=openai_messages,
                        model="claude-3-5-sonnet-latest",
                    ) as stream:
                        for text in stream.text_stream:
                            if client_disconnected():
                                logger.info("Client disconnected, stopping Claude stream.")
                                stream.close()  # Official stop method
                                break
                            yield text
                except Exception as e:
                    logger.error(f"Claude streaming error: {e}")

            return StreamingHttpResponse(claude_event_stream(), content_type='text/plain')

        return StreamingHttpResponse("Invalid model specified.", status=400)
