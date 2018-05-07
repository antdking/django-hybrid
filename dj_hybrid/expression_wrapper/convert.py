from functools import lru_cache
from typing import Any, cast, Optional, Type, Callable, Union, Dict, Tuple, TypeVar, List

import django
from django.db import router, DEFAULT_DB_ALIAS, connections
from django.db.backends.base.base import BaseDatabaseWrapper
from django.db.backends.base.operations import BaseDatabaseOperations
from django.db.models import Model, Expression
from django.db.models.sql.compiler import SQLCompiler

from dj_hybrid.expression_wrapper.base import FakeQuery
from dj_hybrid.expression_wrapper.types import SupportsConversion

T_SupportsConversion = TypeVar('T_SupportsConversion', bound=SupportsConversion)

ConverterNew = Callable[[Any, T_SupportsConversion, BaseDatabaseWrapper], Any]
ConverterOld = Callable[[Any, T_SupportsConversion, BaseDatabaseWrapper, Dict], Any]
Converter = Union[ConverterNew, ConverterOld]
ConvertersExpressionPair = Tuple[List[Converter], T_SupportsConversion]
ConverterDict = Dict[int, Tuple[List[Converter], T_SupportsConversion]]


def get_converters(expression: T_SupportsConversion, model: Model) -> ConvertersExpressionPair:
    db = get_db(model)
    if isinstance(model, Model):
        model = model._meta.model
    compiler = get_compiler_instance(db, model)
    return get_converters_with_compiler(expression, compiler)


@lru_cache()
def get_converters_with_compiler(
    expression: T_SupportsConversion,
    compiler: SQLCompiler
) -> ConvertersExpressionPair:
    converters = compiler.get_converters([expression])  # type: ConverterDict
    if not converters:
        return [], expression
    return converters[0]


if django.VERSION >= (2,):
    def apply_converters(value: Any, converters_paired: ConvertersExpressionPair, model: Model) -> Any:
        if not converters_paired[0]:
            return value

        db = get_db(model)
        connection = get_connection(db)
        converters, expression = converters_paired
        for converter in converters:
            converter = cast(ConverterNew, converter)
            value = converter(value, expression, connection)
        return value
else:
    def apply_converters(value: Any, converters_paired: ConvertersExpressionPair, model: Model) -> Any:
        if not converters_paired[0]:
            return value

        db = get_db(model)
        connection = get_connection(db)
        converters, expression = converters_paired
        for converter in converters:
            converter = cast(ConverterOld, converter)
            value = converter(value, expression, connection, {})
        return value


def get_db(obj: Union[Any, Type[Any]]) -> str:
    if isinstance(obj, Model):
        return cast(str, router.db_for_read(
            obj._meta.model,
            hints=dict(instance=obj),
        ))
    elif isinstance(obj, type) and issubclass(obj, Model):
        return cast(str, router.db_for_read(obj))
    return DEFAULT_DB_ALIAS


def get_connection(db: str) -> BaseDatabaseWrapper:
    return connections[db]


@lru_cache(maxsize=None)
def get_compiler_cls(db: str) -> Type[SQLCompiler]:
    operations = get_connection(db).ops  # type: BaseDatabaseOperations
    compiler_name = 'SQLCompiler'  # we don't care about other types of compilers
    return cast(Type[SQLCompiler], operations.compiler(compiler_name))


@lru_cache(maxsize=None)
def get_compiler_instance(db: str, model_cls: Type[Model]) -> SQLCompiler:
    compiler_cls = get_compiler_cls(db)
    fake_query = get_fake_query(model_cls)
    return compiler_cls(
        fake_query,
        connection=get_connection(db),
        using=db,
    )


@lru_cache(maxsize=None)
def _get_fake_query(model_or_none: Optional[Type[Model]]) -> FakeQuery:
    return FakeQuery(model=model_or_none)


def get_fake_query(obj: Union[Any, Type[Any]]) -> FakeQuery:
    if isinstance(obj, Model):
        model = obj._meta.model
    elif isinstance(obj, type) and issubclass(obj, Model):
        model = obj
    else:
        model = None
    return _get_fake_query(model)
