from setuptools import setup

tests_require = [
    "pytest-cov",
    "pytest-django",
    "pytest-factoryboy",
    "pytest-mock",
]


setup(
    tests_require=tests_require,
    extras_require={
        'test': tests_require,
    }
)
