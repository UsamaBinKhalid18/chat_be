SECRET_KEY = ''

DEBUG = True

ALLOWED_HOSTS = ['*']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'chatapp',
        'USER': '',
        'PASSWORD': '',
        'HOST': '',
        'PORT': 5432,
    }
}

CORS_ALLOW_HEADERS = (
    'accept',
    'authorization',
    'content-type',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
    'Auth-Token',
)

# CSRF_TRUSTED_ORIGINS = ['*']

CORS_ORIGIN_ALLOW_ALL = True

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'APP': {
            'client_id': '123',
            'secret': '456',
            'key': ''
        }
    }
}

FRONTEND_BASE_URL = 'http://localhost:3000'
SOCIALACCOUNT_PROVIDERS['google'] = {
        'APP': {
            'client_id': '',
            'secret': '',
            'key': ''
        },
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        }
    }


PAYMENT_PROCESSORS = {
    'stripe': {
        'processor': 'payments.processors.stripe.Stripe',
        'secret_key': '',
        'webhook_secret_key': '',
    }
}

FRONTEND_PAYMENT_SUCCESS_URL = ''
FRONTEND_PAYMENT_FAILURE_URL = ''
