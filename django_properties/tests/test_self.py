from .utils import not_raises


class CustomException(Exception):
    pass


def test_not_utils():
    exception = CustomException

    def force_raise(): raise exception
    def force_no_raise(): pass

    # no failed assertions will happen if nothing raises
    with not_raises(exception):
        force_no_raise()

    # we need to catch the assertion error. If we get one, great.
    # if we don't, we need to throw our own, as it didn't catch the correct exception
    try:
        with not_raises(exception):
            force_raise()
    except AssertionError as e:
        pass  # we're all good here!
    except exception as e:
        assert not e


