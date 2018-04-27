from dj_hybrid.tests.expression_wrapper.wrapper.factory import WrapperStubFactory
from dj_hybrid.tests.expression_wrapper.wrapper.models import WrapperStubModel
from .base import WrapperTestBase


class RandomTestBase(WrapperTestBase):
    model_class = WrapperStubModel
    factory = WrapperStubFactory

    def test_expression_evaluates_to_expected(self):
        # I'm unsure on how to test randomness here. I could use a mock, but..
        pass

    def test_parity_with_database(self):
        # we can't actually test parity, however we can check the return types
        model_instance = self.get_populated_model()
        python_outcome = self.get_as_python(model_instance)
        database_outcome = self.get_from_database(model_instance)

        assert type(python_outcome) is type(database_outcome)
