from typing import Any, Callable, Optional, Type, TypeVar, Union, cast, overload

from django.db.models import ExpressionWrapper, Expression, F
from .expression_wrapper.types import Wrapable
from .expression_wrapper.wrap import wrap
from .types import SupportsPython

T = TypeVar('T')
V_Class = TypeVar('V_Class', bound=Wrapable)
HybridMethodType = Callable[[Type[T]], V_Class]


class HybridProperty(classmethod):
    __slots__ = (
        'func',
        'name',
        '_cached_expression',
        '_cached_wrapped',
    )

    def __init__(self,
                 func: HybridMethodType,
                 *,
                 name: Optional[str] = None) -> None:
        super().__init__(func)
        self.func = func
        self.name = name or func.__name__
        self._cached_expression = None  # type: Optional[Wrapable]
        self._cached_wrapped = None  # type: Optional[SupportsPython]

    @overload
    def __get__(self, instance: T, owner: Optional[Type[T]] = None) -> Any:
        ...

    @overload
    def __get__(self, instance: None, owner: Type[T]) -> V_Class:
        ...

    def __get__(self, instance: Optional[T], owner: Optional[Type[T]] = None) -> Union[Any, V_Class]:
        if instance is None:
            return self.class_method_behaviour(cast(Type[T], owner))
        return self.instance_method_behaviour(instance)

    def reset_cache(self) -> None:
        self._cached_expression = None
        self._cached_wrapped = None

    def __del__(self) -> None:
        self.reset_cache()

    def __set_name__(self, owner: Type[T], name: str) -> None:
        self.name = name

    def class_method_behaviour(self, owner: Type[T]) -> V_Class:
        if self._cached_expression is None:
            self._cached_expression = NamedExpression(self.func(owner), self.name)
        return cast(V_Class, self._cached_expression)

    def instance_method_behaviour(self, instance: T) -> Any:
        if self._cached_wrapped is None:
            self._cached_wrapped = wrap(
                self.func(type(instance))
            )
        return self._cached_wrapped.as_python(instance)


class NamedExpression(ExpressionWrapper):  # type: ignore
    def __init__(self, expression: Union[Expression, F], default_alias: str) -> None:
        super().__init__(expression, None)
        self.default_alias = default_alias
