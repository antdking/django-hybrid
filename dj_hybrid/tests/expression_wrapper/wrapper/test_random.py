from django.db.models.expressions import Random

from dj_hybrid.tests.expression_wrapper.wrapper.factory import WrapperStubFactory
from dj_hybrid.tests.expression_wrapper.wrapper.models import WrapperStubModel
import dj_hybrid.expression_wrapper.wrappers
from .base import WrapperTestBase


class TestRandom(WrapperTestBase):
    model_class = WrapperStubModel
    factory = WrapperStubFactory
    expression = Random()

    def test_expression_evaluates_to_expected(self, mocker):
        expected = 0.56
        mocker.patch('dj_hybrid.expression_wrapper.wrappers.random.random', return_value=expected)
        model_instance = self.get_populated_model()
        python_outcome = self.get_as_python(model_instance)
        assert python_outcome == expected

    def test_parity_with_database(self):
        # we can't actually test parity, however we can check the return types
        model_instance = self.get_populated_model()
        python_outcome = self.get_as_python(model_instance)
        database_outcome = self.get_from_database(model_instance)

        assert type(python_outcome) is type(database_outcome)

    def test_cached_per_instance(self):
        instance_1 = self.factory()
        instance_2 = self.factory()
        wrapped = self.get_wrapped()

        assert wrapped.as_python(instance_1) is wrapped.as_python(instance_1)
        assert wrapped.as_python(instance_2) is wrapped.as_python(instance_2)
        assert wrapped.as_python(instance_1) is not wrapped.as_python(instance_2)

