from typing import Callable, TypeVar, Type, overload, Optional, Union, Any, cast

from .expression_wrapper.types import Wrapable
from .expression_wrapper.wrap import wrap
from .types import SupportsPython

T = TypeVar('T')
V_Class = TypeVar('V_Class', bound=Wrapable)
HybridMethodType = Callable[[Type[T]], V_Class]


class Hybrid:
    __slots__ = (
        'func',
        'name',
        '_cached_expression',
        '_cached_wrapped',
    )

    def __init__(self,
                 func: HybridMethodType,
                 name: Optional[str] = None) -> None:
        self.func = func
        self.name = name or func.__name__
        self._cached_expression = None  # type: Optional[Wrapable]
        self._cached_wrapped = None  # type: Optional[SupportsPython]

    @overload
    def __get__(self, instance: T, owner: Type[T]) -> Any:
        ...

    @overload
    def __get__(self, instance: None, owner: Type[T]) -> V_Class:
        ...

    def __get__(self, instance: Optional[T], owner: Type[T]) -> Union[Any, V_Class]:
        if instance is None:
            return self.class_method_behaviour(owner)
        return self.instance_method_behaviour(instance)

    def __set__(self, instance: T, value: Any) -> None:
        instance.__dict__[self.name] = value

    def __del__(self) -> None:
        self._cached_expression = None
        self._cached_wrapped = None

    def __set_name__(self, owner: Type[T], name: str) -> None:
        self.name = name

    def class_method_behaviour(self, owner: Type[T]) -> V_Class:
        if self._cached_expression is None:
            self._cached_expression = self.func(owner)
        return cast(V_Class, self._cached_expression)

    def instance_method_behaviour(self, instance: T) -> Any:
        if self._cached_wrapped is None:
            self._cached_wrapped = wrap(
                self.class_method_behaviour(type(instance))
            )
        return self._cached_wrapped.as_python(instance)


hybrid = Hybrid
