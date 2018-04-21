from typing import TypeVar, TYPE_CHECKING, Type, Union, Callable, overload, Dict, Optional, Mapping, MutableMapping

if TYPE_CHECKING:
    from django.db.models import Expression, Lookup, F, Q
    from django_properties.expression_wrapper.base import ExpressionWrapper

# technically anything can be registered, but let's stick with this..
Registrable = Union[Type['Expression'], Type['Lookup'], Type['F'], Type['Q']]
Wrapper = Union[Type['ExpressionWrapper'], Callable[[Registrable], 'ExpressionWrapper']]
Registrable_T = TypeVar('Registrable_T', bound=Registrable)
Wrapper_T = TypeVar('Wrapper_T', bound=Wrapper)
RegistryDict = Dict[Registrable, Wrapper]


class Registry:

    def __init__(self) -> None:
        self.registry = {}  # type: RegistryDict

    @overload
    def register(self, expression: Registrable, wrapper: Wrapper_T) -> Wrapper_T:
        ...

    @overload
    def register(
        self,
        expression: Registrable,
        wrapper: None = None
    ) -> Callable[[Wrapper_T], Wrapper_T]:
        ...

    def register(  # type: ignore  # these are defined in overload, but it's causing an undue conflict
        self,
        expression: Registrable,
        wrapper: Optional[Wrapper_T] = None
    ) -> Union[Wrapper_T, Callable[[Wrapper_T], Wrapper_T]]:

        if wrapper is None:
            def outer(actual_wrapper: Wrapper_T) -> Wrapper_T:
                nonlocal expression, self
                return self._register(expression, actual_wrapper)
            return outer

        return self._register(expression, wrapper)

    def _register(self, expression: Registrable, wrapper: Wrapper_T) -> Wrapper_T:
        if expression in self.registry:
            raise ValueError("Already in registry")
        self.registry[expression] = wrapper
        return wrapper

    def unregister(self, expression: Registrable) -> None:
        self.registry.pop(expression, None)

    def get(self, expression: Registrable) -> Wrapper:
        return self.registry[expression]


registry = Registry()
register = registry.register
