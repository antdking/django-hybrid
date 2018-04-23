from contextlib import contextmanager

from typing import Union, Type


ExceptionType = Union[BaseException, Type[BaseException]]


@contextmanager
def not_raises(exception: ExceptionType) -> None:
    try:
        yield
    except exception as e:
        raise AssertionError("Did raise: {}".format(e))
