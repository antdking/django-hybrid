from typing import Any, Callable, Optional, Type, TypeVar, Union, cast, overload, Tuple, Sequence, Generator

from django.db.models import ExpressionWrapper, Expression, F
from django.db.models.constants import LOOKUP_SEP

from dj_hybrid.expression_wrapper.convert import get_fake_query, get_converters, apply_converters
from .expression_wrapper.types import Wrapable, SupportsResolving, SupportsConversion, Wrapper
from .expression_wrapper.wrap import wrap
from .types import SupportsPython

T = TypeVar('T')
V_Class = TypeVar('V_Class', bound=Wrapable)
HybridMethodType = Callable[[Type[T]], V_Class]
InstanceMethodCacheType = Tuple[SupportsPython, SupportsConversion]


class HybridProperty:
    __slots__ = (
        'func',
        'name',
        '_cached_expression',
        '_instance_method_cache',
    )
    is_hybrid = True

    def __init__(self,
                 func: HybridMethodType,
                 *,
                 name: Optional[str] = None) -> None:
        super().__init__()
        self.func = func
        self.name = name or func.__name__
        self._cached_expression = None  # type: Optional['HybridWrapper']
        self._instance_method_cache = None  # type: Optional[InstanceMethodCacheType]

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

    def reset_cache(self) -> None:
        self._cached_expression = None
        self._instance_method_cache = None

    def __del__(self) -> None:
        self.reset_cache()

    def __set_name__(self, owner: Type[T], name: str) -> None:
        self.name = name

    def class_method_behaviour(self, owner: Type[T]) -> 'HybridWrapper':
        if self._cached_expression is None:
            self._cached_expression = HybridWrapper(self.func(owner), self.name, owner)
        return self._cached_expression

    def _populate_instance_method_cache(self, instance: T) -> None:
        wrapped = wrap(self.func(type(instance)))
        if isinstance(wrapped, SupportsResolving):
            wrapped = wrapped.resolve_expression(get_fake_query(instance))
        if isinstance(wrapped, SupportsConversion):
            for_conversion = wrapped
        elif isinstance(wrapped, Wrapper):
            for_conversion = wrapped.get_for_conversion()
        else:
            raise ValueError("Can't get expression for conversion")
        self._instance_method_cache = wrapped, for_conversion

    def instance_method_behaviour(self, instance: T) -> Any:
        if self._instance_method_cache is None:
            self._populate_instance_method_cache(instance)
        if self._instance_method_cache is None:
            raise Exception("Unable to generate expression")

        expression, converter_expression = self._instance_method_cache
        value = expression.as_python(instance)
        converters = get_converters(converter_expression, instance)
        value = apply_converters(value, converters, instance)
        return value


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
