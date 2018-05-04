from typing import Any, Callable, Optional, Type, TypeVar, Union, cast, overload, Sequence, Generator

from django.db.models import ExpressionWrapper, Expression, F
from django.db.models.constants import LOOKUP_SEP

from dj_hybrid.types import Slots
from .expression_wrapper.types import Wrapable
from .expression_wrapper.wrap import wrap

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
    is_hybrid = True

    def __init__(self,
                 func: HybridMethodType,
                 *,
                 name: Optional[str] = None) -> None:
        super().__init__(func)
        self.func = func
        self.name = name or func.__name__

    @overload
    def __get__(self, instance: T, owner: Optional[Type[T]] = None) -> Any:
        ...

    @overload
    def __get__(self, instance: None, owner: Type[T]) -> 'HybridWrapper':
        ...

    def __get__(self, instance: Optional[T], owner: Optional[Type[T]] = None) -> Union[Any, 'HybridWrapper']:
        if instance is None:
            return self.class_method_behaviour(cast(Type[T], owner))
        return self.instance_method_behaviour(instance)

    def __set_name__(self, owner: Type[T], name: str) -> None:
        self.name = name

    def class_method_behaviour(self, owner: Type[T]) -> 'HybridWrapper':
        return HybridWrapper(self.func(owner), self.name, owner)

    def instance_method_behaviour(self, instance: T) -> Any:
        return wrap(self.func(type(instance))).as_python(instance)


class HybridWrapper(ExpressionWrapper):  # type: ignore
    def __init__(self, expression: V_Class, default_alias: str, owner: Type[T]) -> None:
        super().__init__(expression, None)
        self.default_alias = default_alias
        self.owner = owner

    def with_dependencies(self) -> Sequence['HybridWrapper']:
        dependencies = [self]
        for f in find_f(self):
            if LOOKUP_SEP in f.name:
                raise NotImplementedError("can't resolve a relation yet")

            dependency_property = self.owner.__dict__.get(f.name, None)
            if getattr(dependency_property, 'is_hybrid', False):
                dependencies.append(getattr(self.owner, f.name))

        return dependencies


def find_f(expression: Union[Expression, F]) -> Generator[F, None, None]:
    if isinstance(expression, F):
        yield expression
    else:
        for source in expression.get_source_expressions():
            yield from find_f(source)
