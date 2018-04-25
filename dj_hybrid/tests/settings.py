SECRET_KEY = 'fake-key'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
    }
}

INSTALLED_APPS = [
    'dj_hybrid',
    'dj_hybrid.tests.expression_wrapper.wrapper',
]
