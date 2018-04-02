

class ExpressionWrapper:
    def __init__(self, expression):
        self.expression = expression

    def as_python(self, obj):
        raise NotImplementedError
