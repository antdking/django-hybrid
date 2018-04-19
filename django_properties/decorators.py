from typing import Callable, TypeVar, Type, overload

from django.db.models import Expression, F

from django_properties.expression_wrapper import wrap
from django_properties.expression_wrapper.base import ExpressionWrapper

T = TypeVar('T')
V_Class = TypeVar('V_Class', Expression, F)
V_Instance = TypeVar('V_Instance')
HybridMethodType = Callable[[T], V_Class]

_UNSET = object()


class Hybrid:
    __slots__ = (
        'func',
        'name',
        '_cached_expression',
        '_cached_wrapped',
    )

    def __init__(self,
                 func: HybridMethodType,
                 name: str = None):
        self.func = func
        self.name = name or func.__name__
        self._cached_expression = _UNSET  # type: V_Class
        self._cached_wrapped = _UNSET  # type: ExpressionWrapper

    @overload
    def __get__(self, instance: T, owner: Type[T]) -> V_Instance:
        ...

    @overload
    def __get__(self, instance: None, owner: Type[T]) -> V_Class:
        ...

    def __get__(self, instance, owner):
        if instance is None:
            return self.class_method_behaviour(owner)
        return self.instance_method_behaviour(instance)

    def __set__(self, instance: T, value: V_Instance) -> None:
        instance.__dict__[self.name] = value

    def __del__(self):
        self._cached_expression = _UNSET

    def __set_name__(self, owner: Type[T], name: str):
        self.name = name

    def class_method_behaviour(self, owner: Type[T]) -> V_Class:
        if self._cached_expression is _UNSET:
            self._cached_expression = self.func(owner)
        return self._cached_expression

    def instance_method_behaviour(self, instance: T) -> V_Instance:
        if self._cached_wrapped is _UNSET:
            self._cached_wrapped = wrap(
                self.class_method_behaviour(type(instance))
            )
        return self._cached_wrapped.as_python(instance)


hybrid = Hybrid
