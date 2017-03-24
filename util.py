import datetime
import enum
import random
from json import JSONEncoder as BaseJSONEncoder
from typing import Any, List, Dict


def generate_hex_string(length):
    return '%x' % random.SystemRandom().getrandbits(length * 4)


def get_attrs(obj: object, attrs: List[str], include_none=True) -> Dict[str, Any]:
    return {attr: getattr(obj, attr) for attr in attrs if include_none or getattr(obj, attr) is not None}


def column_dict(obj, include_none=True) -> Dict[str, Any]:
    return get_attrs(obj, [column.name for column in obj.__table__.columns], include_none=include_none)


# This doesn't play well with deserialization
class JSONEncoder(BaseJSONEncoder):
    def default(self, obj: object):
        if isinstance(obj, enum.Enum):
            return obj.value
        elif isinstance(obj, datetime.datetime):
            return obj.timestamp()
        return BaseJSONEncoder.default(self, obj)


def partial(func, *args, **kwargs):
    def newfunc(*fargs, **fkwargs):
        newkwargs = kwargs.copy()
        newkwargs.update(fkwargs)
        return func(*args, *fargs, **newkwargs)
    newfunc.func = func
    newfunc.args = args
    newfunc.kwargs = kwargs
    return newfunc
