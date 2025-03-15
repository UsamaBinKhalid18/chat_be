import os
from django.conf import settings
from django.core.asgi import get_asgi_application
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


fastapp = FastAPI()

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'your_django_project.settings')

django_app = get_asgi_application()

fastapp.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Do not move this import to the top of the file
# to avoid circular import issues

from chat_completion.api.fastapi.views import chat_router  # noqa isort:skip E402

fastapp.include_router(chat_router)


# Mount FastAPI app under a specific path (e.g., /api/fastapi)
app = FastAPI()
app.mount("/api/fastapi", fastapp)
app.mount("/", django_app)

# Optionally serve static files (if needed)
# app.mount("/static", StaticFiles(directory="static"), name="static")
