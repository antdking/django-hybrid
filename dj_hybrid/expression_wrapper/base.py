import copy
from typing import TYPE_CHECKING, Any, Generic, Tuple, TypeVar, cast, Type, Dict, Optional, ClassVar, Union

from dj_hybrid.utils import cached_property

from .types import Wrapable, Wrapper

if TYPE_CHECKING:
    from django.db.models import Q, Model
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
        # We need to do some faking of the ref resolution.
        # This essentially enables us to have a bit more complete
        # workings of F().
        return Col(name, None)

    @staticmethod
    def _add_q(node: T_Q, *_: Any, **__: Any) -> Tuple[T_Q, None]:
        return node, None

    @staticmethod
    def promote_joins(*_: Any, **__: Any) -> None:
        pass


class ExpressionWrapper(Wrapper, Generic[T_Wrapable]):
    __slots__ = ('expression',)

    def __init__(self, expression: T_Wrapable) -> None:
        super().__init__(expression)
        self.expression = expression

    @property
    def resolved_expression(self) -> T_Wrapable:
        # ok, this is a bit of a lie. This can infact return any Wrapable, however
        # for most cases, it will be of the same type as to what we're dealing with.
        if hasattr(self.expression, 'resolve_expression'):
            return cast(T_Wrapable, self.expression.resolve_expression(FakeQuery))
        return self.expression

