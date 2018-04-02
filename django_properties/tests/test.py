import unittest

from django.db.models import Value, F
from django.test import TestCase

from django_properties import expression_wrapper


class WrapperTestCase(TestCase):

    def test_value(self):
        value = Value("test")
        wrapped_value = expression_wrapper.wrap(value)
        python_value = wrapped_value.as_python(None)
        self.assertEqual(python_value, "test")

    def test_field(self):
        field = F('field')
        obj = type('', (object,), dict(field='test'))

        wrapped_field = expression_wrapper.wrap(field)
        python_value = wrapped_field.as_python(obj)
        self.assertEqual(python_value, 'test')
