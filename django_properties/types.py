from typing import Any

from typing_extensions import Protocol


class SupportsPython(Protocol):
    def as_python(self, obj: Any) -> Any: ...


class SupportsPythonComparison(SupportsPython, Protocol):
    def as_python(self, obj: Any) -> bool: ...
