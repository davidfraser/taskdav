#!/usr/bin/env python

"""helpers for testing etc"""

def raises(ExpectedException, target, *args, **kwargs):
    """raise AssertionError, if target code does not raise the expected exception"""
    try:
        result = target(*args, **kwargs)
    except ExpectedException as e:
        return True
    except Exception as e:
        raise AssertionError("Call to %s did not raise %s but raised %s: %s" % (target.__name__, ExpectedException.__name__, e.__class__.__name__, e))
    raise AssertionError("Call to %s did not raise %s but returned %r" % (target.__name__, ExpectedException.__name__, result))

def not_raises(UnexpectedException, target, *args, **kwargs):
    """raise AssertionError, if target code raises the given unexpected exception"""
    try:
        result = target(*args, **kwargs)
    except UnexpectedException as e:
        raise AssertionError("Call to %s raised %s: %s" % (target.__name__, e.__class__.__name__, e))
    return result

