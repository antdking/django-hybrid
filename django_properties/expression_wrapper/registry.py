from functools import partial


class Registry:
    def __init__(self):
        self.registry = {}

    def register(self, expression, wrapper=None):
        if wrapper is None:
            # we're inside a decorator
            return partial(self._register, expression)
        return self._register(expression, wrapper)

    def _register(self, expression, wrapper):
        if expression in self.registry:
            raise ValueError("Already in registry")
        self.registry[expression] = wrapper
        return wrapper

    def unregister(self, expression):
        self.registry.pop(expression, None)

    def get(self, expression):
        return self.registry[expression]


registry = Registry()
register = registry.register
