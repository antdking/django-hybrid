import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_properties.test.settings')


import django
django.setup()


from django.core.management import call_command


if __name__ == '__main__':
    call_command('test', *sys.argv[1:])
