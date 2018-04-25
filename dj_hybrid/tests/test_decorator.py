from functools import partial
from inspect import signature
from unittest.mock import Mock

from django.db.models import F
from pytest import raises

import dj_hybrid
from dj_hybrid import decorator, hybrid_property
from dj_hybrid.decorator import HybridProperty, NamedExpression
from .utils import not_raises, are_equal


def get_some_class():
    # we wrap this so that we get a clean cache on each test
    class SomeClass:
        def __init__(self, int_field=1, char_field="hello"):
            self.int_field = int_field
            self.char_field = char_field

        @hybrid_property
        def int_field_alias(cls):
            return F('int_field')

        @dj_hybrid.property
        def char_field_alias(cls):
            return F('char_field')

        @dj_hybrid.property
        def add_2(cls):
            return cls.int_field_alias + 20
    return SomeClass


def test_interface():
    assert hybrid_property is dj_hybrid.property is HybridProperty

    # we follow an uncalled decorator pattern, return_value=None
    # essentially. @hybrid, not @hybrid()
    sig = signature(hybrid_property)
    with not_raises(TypeError):
        sig.bind(object)

    # we also support wrapping a function when defining a name
    with not_raises(TypeError):
        sig.bind(object, name="some_name")

    # but we don't support setting the name implicitly
    with raises(TypeError):
        sig.bind(object, "some_name")


def test_int_field_alias__class():
    expected = NamedExpression(F('int_field'), 'int_field_alias')
    actual = get_some_class().int_field_alias
    assert are_equal(expected, actual)


def test_int_field_alias__instance():
    expected = 1
    SomeClass = get_some_class()
    actual = SomeClass(int_field=expected).int_field_alias
    assert expected == actual


def test_caching_behaviour__class(mocker):
    mocked_named = mocker.spy(NamedExpression, '__init__')  # type: Mock
    SomeClass = get_some_class()
    first = SomeClass.int_field_alias
    second = SomeClass.int_field_alias
    assert mocked_named.call_count == 1
    assert first is second
    SomeClass.__dict__['int_field_alias'].reset_cache()
    third = SomeClass.int_field_alias
    assert mocked_named.call_count == 2
    assert third is not first
    assert are_equal(first, third)


def test_caching_behaviour__instance(mocker):
    mocked_wrap = mocker.spy(decorator, 'wrap')  # type: Mock
    SomeClass = get_some_class()
    instance = SomeClass(char_field="hello")

    descriptor = SomeClass.__dict__['char_field_alias']

    first = instance.char_field_alias
    first_cache = descriptor._cached_wrapped
    second = instance.char_field_alias
    second_cache = descriptor._cached_wrapped

    assert first is second
    assert first_cache is second_cache
    assert mocked_wrap.call_count == 1

    SomeClass.__dict__['char_field_alias'].reset_cache()
    assert not descriptor._cached_wrapped

    third = instance.char_field_alias
    third_cache = descriptor._cached_wrapped
    assert first_cache is not third_cache
    assert are_equal(first_cache, third_cache)
    assert first is third
    assert mocked_wrap.call_count == 2
