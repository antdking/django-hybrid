from django.test import TestCase


class StubTestCase(TestCase):
    def test_stub(self):
        self.assertEqual(1, 1)
