import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_properties.tests.settings')


import django
from django.core.management import call_command


def runtests(*test_args):
    print(test_args)
    django.setup()
    call_command('test')


if __name__ == '__main__':
    runtests(*sys.argv[1:])
