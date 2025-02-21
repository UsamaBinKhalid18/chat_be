from django.http import JsonResponse, StreamingHttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from google import genai
from django.conf import settings
from openai import OpenAI
from anthropic import Anthropic
import logging
import base64


from chat_completion.models import FileUpload
from chat_completion.permissions import IsSubscribed
from chat_completion.api.v1.serializers import FileUploadSerializer


logger = logging.getLogger(__name__)


class ChatCompletionView(APIView):
    http_method_names = ['post']
    permission_classes = [IsSubscribed]

    def post(self, request):
        model = request.data.get('model')
        messages = request.data.get('messages', [])

        if not messages:
            return StreamingHttpResponse("No messages provided.", status=400)
        for msg in messages:
            if msg.get('fileId'):
                file = FileUpload.objects.filter(uuid=msg['fileId']).first()
                if file:
                    msg['file'] = file

        # 🔹 Gemini 1.5 Pro
        if model == 'Google Gemini 1.5':
            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            gemini_messages = [
                {
                    "role": 'user' if msg['isUser'] else 'assistant',
                    "parts": [
                        {"text": msg['text']},  # Always include the text
                        # Conditionally include file_data
                        *([
                            {"text": f'user uploaded a file named: {msg["file"].original_name}'}]
                            if msg.get('file')
                            else []),
                        *([
                            {"inline_data": {
                                "data": base64.b64encode(msg['file'].file.read()).decode("utf-8"),
                                "mime_type": msg['file'].content_type,
                            }}] if msg.get('file') else [])
                    ]
                }
                for msg in messages
            ]

            def gemini_event_stream():
                try:
                    response = client.models.generate_content_stream(model='gemini-2.0-flash', contents=gemini_messages)
                    for chunk in response:
                        yield chunk.text
                except GeneratorExit:
                    logger.info("Client disconnected, stopping Gemini stream.")
                except Exception as e:
                    logger.error(f"Gemini streaming error: {e}")
                    yield "Couldn't get a response. If this persists, please contact support."

            return StreamingHttpResponse(gemini_event_stream(), content_type='text/plain')

        if model in ['OpenAI GPT 4o Mini', 'OpenAI GPT 4o']:
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            openai_messages = [
                {
                    "role": 'user' if msg['isUser'] else 'assistant',
                    "content": [
                        {"type": "text", "text": msg["text"]},
                        *([{"type": "image_url", "image_url": {'url': f'${settings.BASE_URL}${file.file.url}'}}]
                          if ((file := msg.get('file')) and 'image' in file.content_type) else []),
                        *([{'type': 'text', 'text': f'user uploaded a file file content in bytes: {str(file.file.read())}'}]
                          if (file := msg.get('file')) and 'image' not in file.content_type else [])
                    ]
                }
                for msg in messages
            ]

            def openai_event_stream():
                try:
                    response = client.chat.completions.create(
                        model="gpt-4o-mini" if model == "GPT 4o Mini" else "gpt-4o",
                        messages=openai_messages,
                        stream=True
                    )
                    for chunk in response:
                        yield chunk.choices[0].delta.content or ""
                except GeneratorExit:
                    logger.info("Client disconnected, stopping OpenAI stream.")
                    response.close()
                except Exception as e:
                    logger.error(f"OpenAI streaming error: {e}")
                    yield "Couldn't get a response. If this persists, please contact support."

            return StreamingHttpResponse(openai_event_stream(), content_type='text/plain')

        # 🔹 Claude 3.5 Sonnet
        if model == 'Anthropic Claude':
            anthropic_messages = [
                {
                    "role": 'user' if msg['isUser'] else 'assistant',
                    "content": [
                        {"type": "text", "text": msg["text"]},
                        *([{
                            "type": "image",
                            "source": {
                                'type': 'base64',
                                'media_type': file.content_type,
                                'data': base64.b64encode(file.file.read()).decode("utf-8")
                            }}]
                            if ((file := msg.get('file')) and 'image' in file.content_type) else []),
                        *([{
                            "type": "text",
                            "text": f'user uploaded a file named: {file.original_name}, file content in bytes: {str(file.file.read())}'}]
                            if ((file := msg.get('file')) and 'image' not in file.content_type) else [])
                    ]
                }
                for msg in messages
            ]
            client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)

            def claude_event_stream():
                try:
                    with client.messages.stream(
                        max_tokens=1024,
                        messages=anthropic_messages,
                        model="claude-3-5-sonnet-latest",
                    ) as stream:
                        for text in stream.text_stream:
                            yield text
                except GeneratorExit:
                    logger.info("Client disconnected, stopping Claude stream.")
                    stream.close()
                except Exception as e:
                    logger.error(f"Claude streaming error: {e}")
                    yield "Couldn't get a response. If this persists, please contact support."

            return StreamingHttpResponse(claude_event_stream(), content_type='text/plain')

        return StreamingHttpResponse("Invalid model specified.", status=400)


class FileUploadView(APIView):
    http_method_names = ['post', 'delete']
    permission_classes = [IsSubscribed]
    serializer_class = FileUploadSerializer

    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return Response("No file provided.", status=400)

        file = FileUpload.objects.create(file=file, original_name=file.name, content_type=file.content_type)
        ser = self.serializer_class(file)
        return JsonResponse(ser.data)

    def delete(self, request):
        file_id = request.data.get('id')
        if not file_id:
            return Response("No file ID provided.", status=400)
        file = FileUpload.objects.filter(uuid=file_id).first()
        if file:
            file.delete()
        return Response("File deleted successfully", status=200)
