from inspect import Signature

from dj_hybrid.expression_wrapper import wrap
from dj_hybrid.expression_wrapper.registry import registry
from dj_hybrid.tests.utils import not_raises


class FakeSupportsPython:
    def as_python(self, obj):
        ...


class FakeWrapper:
    def __init__(self, expression):
        self.expression = expression


def test_wrap_signature():
    signature = Signature.from_callable(wrap.wrap)
    with not_raises(TypeError):
        signature.bind(object())
        signature.bind(expression=object())


def test_wrap_wraps(mocker):
    mocker.patch('dj_hybrid.expression_wrapper.wrap.registry.get', return_value=FakeWrapper)

    obj_to_wrap = object()
    wrapped = wrap.wrap(obj_to_wrap)
    assert isinstance(wrapped, FakeWrapper)
    assert wrapped.expression is obj_to_wrap


def test_wrap_ignores_python_supported():
    obj_to_wrap = FakeSupportsPython()
    wrapped = wrap.wrap(obj_to_wrap)
    assert wrapped is obj_to_wrap


def test_get_wrapper():
    ObjToRegister = type('ObjToRegister', (object,), {})
    registry.register(ObjToRegister, FakeWrapper)

    assert wrap.get_wrapper(ObjToRegister) is FakeWrapper
    assert wrap.get_wrapper(ObjToRegister()) is FakeWrapper

    registry.unregister(ObjToRegister)
