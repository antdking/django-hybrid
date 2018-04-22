from typing import Any, Callable, Generic, Mapping, Optional, Type, TypeVar, Union, overload

from django.utils.functional import cached_property as django_cached_property

ObjectStructure = Mapping[str, Any]
NestedItemCallable = Callable[[ObjectStructure], Any]


def nested_itemgetter(item: str) -> NestedItemCallable:
    def inner(obj: ObjectStructure) -> Any:
        return resolve_item(obj, item)
    return inner


def resolve_item(obj: ObjectStructure, item: str) -> Any:
    for key in item.split('.'):
        obj = obj[key]
    return obj


T = TypeVar('T')
R = TypeVar('R')


class cached_property(django_cached_property, Generic[T, R]):  # type: ignore
    def __init__(self, func: Callable[[T], R], name: Optional[str] = None) -> None:
        super().__init__(func, name=name)

    @overload
    def __get__(self, instance: None, cls: Optional[Type[T]] = None) -> 'cached_property[T, R]':
        ...

    @overload
    def __get__(self, instance: T, cls: Optional[Type[T]] = None) -> R:
        ...

    def __get__(self, instance: Optional[T], cls: Optional[Type[T]] = None) -> Union['cached_property[T, R]', R]:
        return super().__get__(instance, cls)  # type: ignore
