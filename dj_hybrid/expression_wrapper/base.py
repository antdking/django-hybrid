import copy
from typing import TYPE_CHECKING, Any, Generic, Tuple, TypeVar, Type, Dict, Optional, ClassVar

from dj_hybrid.types import SupportsPython

from .types import Wrapable, Wrapper

if TYPE_CHECKING:
    from django.db.models import Q, Model, Field
    from django.db.models.expressions import Col
    from django.db.models.sql import Query


T_Q = TypeVar('T_Q', bound='Q')
T_Wrapable = TypeVar('T_Wrapable', bound=Wrapable)


class FakeQuery:
    __slots__ = (
        'model',
        'context',
    )

    for_python = True  # type: ClassVar[bool]

    def __init__(self, model: Optional[Type['Model']] = None) -> None:
        self.model = model
        self.context = {}  # type: Dict

    @staticmethod
    def resolve_ref(name: str, *_: Any, **__: Any) -> 'Col':
        from django.db.models.expressions import Col
        from django.db.models.fields import Field
        # We need to do some faking of the ref resolution.
        # This essentially enables us to have a bit more complete
        # workings of F().

        # An interesting point to raise here is, we need to pass a Field in.
        # However, it doesn't need to be the "correct" field. At this point,
        # all conversion has been done, so now we just need to get a valid
        # target in.
        return Col(name, Field())

    @staticmethod
    def _add_q(node: T_Q, *_: Any, **__: Any) -> Tuple[T_Q, None]:
        return node, None

    @staticmethod
    def promote_joins(*_: Any, **__: Any) -> None:
        pass


class ExpressionWrapper(Wrapper, Generic[T_Wrapable]):
    __slots__ = ('expression', '_is_resolved',)

    def __init__(self, expression: T_Wrapable) -> None:
        super().__init__(expression)
        self.expression = expression
        self._is_resolved = False

    def resolve_expression(self, query: FakeQuery) -> SupportsPython:
        if self._is_resolved:
            return self

        c = copy.copy(self)
        c._is_resolved = True
        if hasattr(c.expression, 'resolve_expression'):
            c.expression = c.expression.resolve_expression(query)
        elif hasattr(c.expression, 'copy'):
            c.expression = c.expression.copy()
        else:
            c.expression = copy.copy(c.expression)
        return c

    @property
    def resolved_expression(self):
        return self.resolve_expression(FakeQuery()).expression
