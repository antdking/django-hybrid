from inspect import Signature

from pytest import raises

from django_properties.expression_wrapper import registry
from django_properties.tests.utils import not_raises


def test_interface_exposed():
    assert hasattr(registry, 'register')
    assert hasattr(registry, 'registry')
    assert hasattr(registry.registry, 'register')
    assert hasattr(registry.registry, 'unregister')
    assert hasattr(registry.registry, 'get')

    assert registry.registry.register == registry.register


def test_register_signature():
    signature = Signature.from_callable(registry.register)

    with not_raises(TypeError):
        signature.bind(object(), object())
        signature.bind(object(), wrapper=object())
        signature.bind(expression=object(), wrapper=object())

    # register can behave as a decorator too
    returned_decorator = registry.register(object)
    signature = Signature.from_callable(returned_decorator)

    with not_raises(TypeError):
        signature.bind(object())


def test_unregister_signature():
    signature = Signature.from_callable(registry.registry.unregister)

    with not_raises(TypeError):
        signature.bind(object())


def test_get_signature():
    signature = Signature.from_callable(registry.registry.get)

    with not_raises(TypeError):
        signature.bind(object())


def test_lifecycle():
    key = object()
    val = object()

    registry.registry.register(key, val)
    assert registry.registry.get(key) is val

    assert registry.registry.unregister(key) is None
    with raises(KeyError):
        registry.registry.get(key)

    # and the same with the decorated approach
    registry.registry.register(key)(val)
    assert registry.registry.get(key) is val

    assert registry.registry.unregister(key) is None
    with raises(KeyError):
        registry.registry.get(key)


def test_double_register():
    key = object()
    val = object()

    registry.registry.register(key, val)

    with raises(ValueError, match="Already in registry"):
        registry.registry.register(key, val)

    registry.registry.unregister(key)
