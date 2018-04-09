from abc import abstractmethod
from operator import attrgetter
from typing import Any, Mapping

from django.db.models import Model
from django.db.models.constants import LOOKUP_SEP

from django_properties.utils import nested_itemgetter

_notset = object()


class IResolver:
    __slots__ = (
    )

    @abstractmethod
    def resolve(self, path: str, default: Any = _notset) -> Any:
        ...


class AttributeResolver(IResolver):
    __slots__ = (
        'doc',
    )

    def __init__(self, doc: Any):
        self.doc = doc

    def resolve(self, path: str, default=_notset) -> Any:
        parts = path.split(LOOKUP_SEP)
        attribute_accessor = attrgetter('.'.join(parts))
        return attribute_accessor(self.doc)


class DictResolver(IResolver):
    __slots__ = (
        'doc',
    )

    def __init__(self, doc: Mapping[str, Any]):
        self.doc = doc

    def resolve(self, path: str, default=_notset) -> Any:
        parts = path.split(LOOKUP_SEP)
        item_accessor = nested_itemgetter('.'.join(parts))
        return item_accessor(self.doc)


class DjangoResolver(AttributeResolver):
    pass


def get_resolver(doc):
    if isinstance(doc, Model):
        return DjangoResolver(doc)
    elif isinstance(doc, Mapping):
        return DictResolver(doc)
    else:
        return AttributeResolver(doc)
