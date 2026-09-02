"""Lexical guards on the boundary between Python and the islands.

What is pinned here is not what the transpiler produces but what it REFUSES,
and how: a construct the scanner cannot see must fail by name, not by leaving
CPython to complain about something else.
"""

import pytest

from ldpy.transpiler import transpile, LdpySyntaxError

# CPython then rejected with a message naming nothing. Found by the corpus
# study; refused by name since 0.5.1.

def test_an_island_in_an_fstring_hole_is_refused_by_name():
    src = ('@prefix ex: <http://example.org/> .\n'
           '@graph as g\n'
           't = f"{m{ ?s ex:p ?o }.first()}"\n')
    with pytest.raises(LdpySyntaxError) as e:
        transpile(src, "t.ldpy")
    assert "f-string" in e.value.msg and "m{" in e.value.msg
    assert e.value.line == 2                      # 0-based: the third line


@pytest.mark.parametrize("hole", ["g{ ex:a ex:b 1 }", "s{ SELECT ?s WHERE {} }",
                                  "e{ ?a }", "f<a/{x}>", "_:{1}", "?{1}"])
def test_every_brace_island_is_caught_in_a_hole(hole):
    src = ('@prefix ex: <http://example.org/> .\n'
           '@graph as g\n'
           't = f"{%s}"\n' % hole)
    with pytest.raises(LdpySyntaxError):
        transpile(src, "t.ldpy")


def test_an_ordinary_fstring_is_untouched():
    """The guard must not cost a plain f-string, nor an escaped brace, nor a
    dict display inside a hole."""
    src = ('xs = [1, 2]\n'
           'a = f"{len(xs)} results"\n'
           'b = f"{{literal braces}}"\n'
           'c = f"{ {k: v for k, v in []} }"\n'
           'd = f"{xs!r:>10}"\n')
    code = transpile(src, "t.ldpy").code
    assert 'f"{len(xs)} results"' in code
    assert 'f"{{literal braces}}"' in code


def test_an_island_outside_a_hole_still_works():
    """A comprehension over an island is fine — only the hole is blind."""
    src = ('@prefix ex: <http://example.org/> .\n'
           '@graph as g\n'
           'xs = [s for s in m{ ?s ex:p ?o }]\n')
    assert "_ldpy_.match(" in transpile(src, "t.ldpy").code
