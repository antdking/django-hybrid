import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_properties.tests.settings')


import django
from django.core.management import call_command


def runtests():
    import django.test.utils
    from django.conf import settings
    django.setup()
    runner_class = django.test.utils.get_runner(settings)
    test_runner = runner_class(verbosity=1, interactive=True)
    failures = test_runner.run_tests(['django_properties'])
    sys.exit(failures)


if __name__ == '__main__':
    runtests()
