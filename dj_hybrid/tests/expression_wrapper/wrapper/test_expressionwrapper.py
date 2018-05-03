from django.db.models import ExpressionWrapper, Value, IntegerField, CharField

from .base import WrapperTestBase
from .factory import WrapperStubFactory
from .models import WrapperStubModel


class BaseExpressionWrapperTest(WrapperTestBase):
    model_class = WrapperStubModel
    factory = WrapperStubFactory


class TestStrToInt(BaseExpressionWrapperTest):
    python_value = 20
    expression = ExpressionWrapper(Value("20"), output_field=IntegerField())


class TestIntToStr(BaseExpressionWrapperTest):
    python_value = 20
    expression = ExpressionWrapper(Value(20), CharField())

    # TODO: this test currently fails parity checks.
