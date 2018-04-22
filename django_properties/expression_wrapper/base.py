from typing import TYPE_CHECKING, Any, Union, TypeVar, Tuple, Dict, Generic, cast

from django_properties.expression_wrapper.types import Wrapper, Wrapable
from django_properties.utils import cached_property

if TYPE_CHECKING:
    from django.db.models import Q
    from django.db.models.expressions import Col


T_Q = TypeVar('T_Q', bound='Q')
T_Wrapable = TypeVar('T_Wrapable', bound=Wrapable)

class FakeQuery:
    @classmethod
    def resolve_ref(cls, name: str, *_: Any, **__: Any) -> 'Col':
        from django.db.models.expressions import Col
        # We need to do some faking of the ref resolution.
        # This essentially enables us to have a bit more complete
        # workings of F().
        return Col(name, None)

    @classmethod
    def _add_q(cls, node: T_Q, *_: Any, **__: Any) -> Tuple[T_Q, None]:
        return node, None

    @classmethod
    def promote_joins(cls, *_: Any, **__: Any) -> None:
        pass


class ExpressionWrapper(Wrapper, Generic[T_Wrapable]):
    def __init__(self, expression: T_Wrapable) -> None:
        super().__init__(expression)
        self.expression = expression

    @cached_property
    def resolved_expression(self) -> T_Wrapable:
        # ok, this is a bit of a lie. This can infact return any Wrapable, however
        # for most cases, it will be of the same type as to what we're dealing with.
        if hasattr(self.expression, 'resolve_expression'):
            return cast(T_Wrapable, self.expression.resolve_expression(FakeQuery))
        return self.expression
