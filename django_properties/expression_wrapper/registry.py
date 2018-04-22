from typing import TypeVar, Type, Union, Callable, overload, Dict, Optional

from .types import Wrapable, TypeWrapperOrProxy


Registrable = Type[Wrapable]
T_TypeWrapperOrProxy = TypeVar('T_TypeWrapperOrProxy', bound=TypeWrapperOrProxy)


class Registry:
    def __init__(self) -> None:
        self.registry = {}  # type: Dict[Type[Wrapable], TypeWrapperOrProxy]

    @overload
    def register(self, expression: Registrable, wrapper: T_TypeWrapperOrProxy) -> T_TypeWrapperOrProxy:
        ...

    @overload
    def register(
        self,
        expression: Registrable,
        wrapper: None = None
    ) -> Callable[[T_TypeWrapperOrProxy], T_TypeWrapperOrProxy]:
        ...

    def register(  # type: ignore  # these are defined in overload, but it's causing an undue conflict
        self,
        expression: Registrable,
        wrapper: Optional[T_TypeWrapperOrProxy] = None
    ) -> Union[T_TypeWrapperOrProxy, Callable[[T_TypeWrapperOrProxy], T_TypeWrapperOrProxy]]:

        if wrapper is None:
            def outer(actual_wrapper: T_TypeWrapperOrProxy) -> T_TypeWrapperOrProxy:
                nonlocal expression, self
                return self._register(expression, actual_wrapper)
            return outer

        return self._register(expression, wrapper)

    def _register(self, expression: Registrable, wrapper: T_TypeWrapperOrProxy) -> T_TypeWrapperOrProxy:
        if expression in self.registry:
            raise ValueError("Already in registry")
        self.registry[expression] = wrapper
        return wrapper

    def unregister(self, expression: Registrable) -> None:
        self.registry.pop(expression, None)

    def get(self, expression: Registrable) -> TypeWrapperOrProxy:
        return self.registry[expression]


registry = Registry()
register = registry.register
