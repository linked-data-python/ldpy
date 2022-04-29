# from https://github.com/charmoniumQ/antlr4-python-grun
from typing import TypeVar, Iterator, Tuple, Iterable

Value = TypeVar("Value")

def first_sentinel(iterable: Iterable[Value]) -> Iterator[Tuple[Value, bool]]:
    iterator = iter(iterable)
    yield (next(iterator), True)
    for elem in iterator:
        yield (elem, False)

