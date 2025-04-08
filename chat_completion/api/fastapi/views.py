import base64
import logging
from typing import List, Optional
from anthropic import AsyncAnthropic
from django.conf import settings
from django.core.files.base import ContentFile
from fastapi import APIRouter, Body, Depends, HTTPException, status, UploadFile
from fastapi.security import OAuth2PasswordBearer
import jwt
from openai import AsyncOpenAI
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
from chat_completion.api.v1.serializers import FileUploadSerializer
from chat_completion.models import FileUpload
from payments.models import UserSubscription
from google import genai


chat_router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

logger = logging.getLogger(__name__)


async def decode_token(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        user_id: str = payload.get("user_id")
        if user_id is None:
            raise credentials_exception
        is_subscribed = await UserSubscription.objects.filter(user_id=user_id, is_active=True).aexists()
        if not is_subscribed:
            raise HTTPException(status_code=403, detail="No subscripton")
    except jwt.InvalidTokenError:
        raise credentials_exception


class Message(BaseModel):
    text: str
    isUser: bool
    model: str
    fileId: Optional[str] = None
    file: Optional[UploadFile] = None


class ChatRequest(BaseModel):
    messages: List[Message]
    model: str


MODEL_MAP = {
    'gpt-4': 'gpt-4',
    'gpt-4o': 'gpt-4o',
    'gpt-4o-mini': 'gpt-4o-mini',
    'gpt-o3-mini': 'o3-mini',
    'gpt-o3-mini-high': 'o3-mini-high',
    'deepseek': 'deepseek-chat',
}


@chat_router.post("/chat-completion/", dependencies=[Depends(decode_token)])
async def read_root(data: ChatRequest):
    model = data.model
    messages = data.messages

    if not messages:
        return StreamingResponse("No messages provided.", status_code=400)

    for msg in messages:
        if msg.fileId:
            file = await FileUpload.objects.filter(uuid=msg.fileId).afirst()
            if file:
                msg.file = file

    if model == 'gemini':
        # 🔹 Gemini 1.5 Pro
        client = genai.Client(api_key=settings.GEMINI_API_KEY).aio
        gemini_messages = [
            {
                "role": 'user' if msg.isUser else 'assistant',
                "parts": [
                    {"text": msg.text or ' '},
                    *([
                        {"text": f'user uploaded a file named: {msg.file.original_name}'}]
                        if msg.file
                        else []),
                    *([
                        {"inline_data": {
                            "data": base64.b64encode(msg.file.file.read()).decode("utf-8"),
                            "mime_type": msg.file.content_type,
                        }}] if msg.file else [])
                ]
            }
            for msg in messages
        ]

        async def gemini_event_stream():
            try:
                response = await client.models.generate_content_stream(
                    model='gemini-2.0-flash', contents=gemini_messages
                    )
                async for chunk in response:
                    yield chunk.text
            except GeneratorExit:
                logger.info("Client disconnected, stopping Gemini stream.")
            except Exception as e:
                logger.error(f"Gemini streaming error: {e}")
                logger.error(f"Messages: {gemini_messages}")
                yield "Couldn't get a response. If this persists, please contact support."

        return StreamingResponse(gemini_event_stream())

    if 'gpt' in model or model == 'deepseek':
        if model == 'deepseek':
            client = AsyncOpenAI(api_key=settings.DEEPSEEK_API_KEY, base_url='https://api.deepseek.com')
        else:
            client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        openai_messages = [
            {
                "role": 'user' if msg.isUser else 'assistant',
                "content": [
                    {"type": "text", "text": msg.text},
                    *([{"type": "image_url", "image_url": {'url': f'{settings.BASE_URL}{file.file.url}'}}]
                        if ((file := msg.file) and 'image' in file.content_type) else []),
                    *([{'type': 'text', 'text': f'user uploaded a file file content in bytes: {str(file.file.read())}'}]
                        if (file := msg.file) and 'image' not in file.content_type else [])
                ]
            }
            for msg in messages
        ]

        async def openai_event_stream():
            try:
                response = await client.chat.completions.create(
                    model=MODEL_MAP[model],
                    messages=openai_messages,
                    stream=True
                )
                async for chunk in response:
                    yield chunk.choices[0].delta.content or ""
            except GeneratorExit:
                logger.info("Client disconnected, stopping OpenAI stream.")
                response.close()
            except Exception as e:
                logger.error(f"OpenAI streaming error: {e}")
                logger.error(f"Messages: {openai_messages}")
                yield "Couldn't get a response. If this persists, please contact support."

        return StreamingResponse(openai_event_stream())

    if model == 'claude':
        anthropic_messages = [
            {
                "role": 'user' if msg.isUser else 'assistant',
                "content": [
                        {"type": "text", "text": msg.text or '<no text>'},
                        *([{
                            "type": "image",
                            "source": {
                                'type': 'base64',
                                'media_type': file.content_type,
                                'data': base64.b64encode(file.file.read()).decode("utf-8")
                            }}]
                            if ((file := msg.file) and 'image' in file.content_type) else []),
                        *([{
                            "type": "text",
                            "text": f'user uploaded a file named: {file.original_name}, file content in bytes: {str(file.file.read())}'}]
                            if ((file := msg.file) and 'image' not in file.content_type) else [])
                ]
            }
            for msg in messages
        ]

        client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

        async def claude_event_stream():
            try:
                async with client.messages.stream(
                    max_tokens=1024,
                    messages=anthropic_messages,
                    model="claude-3-7-sonnet-latest",
                ) as stream:
                    async for text in stream.text_stream:
                        yield text
            except GeneratorExit:
                logger.info("Client disconnected, stopping Claude stream.")
                stream.close()
            except Exception as e:
                logger.error(f"Claude streaming error: {e}")
                logger.error(f"Messages: {anthropic_messages}")
                yield "Couldn't get a response. If this persists, please contact support."

        return StreamingResponse(claude_event_stream())

    return StreamingResponse("Invalid model", status_code=400)


@chat_router.post("/upload-file/")
async def upload_file(file: UploadFile):
    file_content = await file.read()
    django_file = ContentFile(file_content, name=file.filename)
    file = await FileUpload.objects.acreate(file=django_file, original_name=file.filename, content_type=file.content_type)
    ser = FileUploadSerializer(file)
    return ser.data
    

class DeleteFile(BaseModel):
    id: str

@chat_router.delete("/delete-file/")
async def delete_file(request: DeleteFile = Body(...)):
    file = await FileUpload.objects.filter(uuid=request.id).afirst()
    if file:
        await file.adelete()
        return "File deleted"
    return "File not found"
