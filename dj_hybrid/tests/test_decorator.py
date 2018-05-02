from functools import partial
from inspect import signature
from unittest.mock import Mock

from django.db.models import F
from pytest import raises

import dj_hybrid
from dj_hybrid import decorator, hybrid_property
from dj_hybrid.decorator import HybridProperty, HybridWrapper
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
        def add_20(cls):
            # same as F('int_field') + 20
            return cls.int_field_alias + 20

        @dj_hybrid.property
        def add_30(cls):
            # same as a1=F('int_field'), a2=F('a1') + 20
            return F('int_field_alias') + 30
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
    klass = get_some_class()
    expected = HybridWrapper(F('int_field'), 'int_field_alias', klass)
    actual = klass.int_field_alias
    assert are_equal(expected, actual)


def test_int_field_alias__instance():
    expected = 1
    SomeClass = get_some_class()
    actual = SomeClass(int_field=expected).int_field_alias
    assert expected == actual


def test_dependency_fetching__no_dependencies():
    klass = get_some_class()
    expected = [klass.int_field_alias]
    actual = klass.int_field_alias.with_dependencies()
    assert are_equal(expected, actual)


def test_reference_hybrid_directly():
    # `add_20` directly references a hybrid. The effect is the expressions are
    # combined, instead of it being treated as a database level reference
    klass = get_some_class()
    expected = [klass.add_20]
    actual = klass.add_20.with_dependencies()
    assert are_equal(expected, actual)


def test_reference_indirectly():
    # looking for dependencies to be detected due to use of `F`
    klass = get_some_class()
    expected = [klass.add_30, klass.int_field_alias]
    actual = klass.add_30.with_dependencies()
    assert are_equal(expected, actual)

