SECRET_KEY = 'fake-key'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
    }
}

INSTALLED_APPS = [
    'django_hybrid',
    'django_hybrid.tests.expression_wrapper.wrapper',
]
