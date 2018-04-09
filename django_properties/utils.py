from typing import Any, Callable, Mapping

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
