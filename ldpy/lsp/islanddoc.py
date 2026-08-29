"""What each island IS, in the three lines a hover shows — record vscode/108.

Per island kind: a signature line in the shape Python tooling uses, a short
prose description, and the documentation page (with anchor) that explains it.
Nothing here knows about LSP; `server.py` renders it, `pygments_lexer.py` and
the semantic tokens name the same kinds.

The table is CLOSED: `tests/test_islanddoc.py` fails when the transpiler grows
a kind with no entry here, and when an anchor no longer exists under `docs/`.
That second test is what keeps the links from rotting silently — a dead link
in a hover is worse than no link, because nothing ever reports it.
"""

DOCS = "https://linked-data-python.readthedocs.io/en/latest/"


class IslandDoc:
    """Signature, description and documentation target of one island kind."""

    __slots__ = ("signature", "summary", "page", "anchor")

    def __init__(self, signature, summary, page, anchor):
        self.signature = signature
        self.summary = summary
        self.page = page            # path under docs/, with the .md suffix
        self.anchor = anchor

    @property
    def url(self):
        """The published URL — mkdocs serves `x/y.md` as `x/y/`."""
        return "%s%s/#%s" % (DOCS, self.page[:-len(".md")], self.anchor)


_TERMS = "reference/language/terms.md"
_DECLS = "reference/language/declarations.md"
_GRAPHS = "reference/language/graphs.md"
_CURRENT = "reference/language/current-graph.md"
_QUERY = "reference/language/querying.md"
_BINDINGS = "reference/language/bindings.md"
_SPARQL_EXPR = "reference/sparql-expressions.md"


ISLANDS = {

    # -- declarations -------------------------------------------------------

    "prefix": IslandDoc(
        "(declaration) @prefix ex: <IRI> .",
        "Binds `ex:` to a namespace IRI for the rest of the enclosing block. "
        "A prefix is lexical: it has no run-time object, and `ex:` on its own "
        "is never a value. Declaring it again in a deeper block shadows it, "
        "the way a Python name would.",
        _DECLS, "prefix-bind-a-prefix"),

    "base": IslandDoc(
        "(declaration) @base <IRI> .",
        "Sets the base against which relative IRIs are resolved for the rest "
        "of the block, so that `<sensor/1>` means `<IRI>sensor/1`.",
        _DECLS, "base-set-the-base-iri"),

    "import": IslandDoc(
        "(declaration) from MODULE import ex:, unit: as u:",
        "Imports prefixes declared by another module, optionally renaming "
        "them. The module is imported as usual; what travels is the prefix "
        "bindings, which have no value to import by ordinary means.",
        _DECLS, "prefixes-across-modules"),

    "graph-decl": IslandDoc(
        "(declaration) @graph EXPR | @graph as NAME -> Graph",
        "Designates the current graph for the block — the one `+{ }`, `-{ }` "
        "and a receiver-less `m{ }` act on. `as NAME` creates a fresh graph "
        "and binds it to NAME; `global` and `nonlocal` widen the scope.",
        _CURRENT, "graph-designate-or-create"),

    "bindings-decl": IslandDoc(
        "(declaration) @bindings EXPR | @bindings as NAME -> Bindings",
        "Designates the current bindings: the mapping that gives `?name` its "
        "value in the enclosing block. Any mapping will do, and `as NAME` "
        "creates an empty one.",
        _BINDINGS, "bindings-the-current-bindings"),

    "for-bindings": IslandDoc(
        "(statement) for @bindings [as NAME] in ITER:",
        "Loops over an iterable of mappings, making each row the current "
        "bindings for the body. A `csv.DictReader` and the solutions of "
        "`m{ }` are both iterables of mappings, so both drive this loop.",
        _BINDINGS, "for-bindings-in-iter-the-loop-that-carries-them"),

    "for-bindings-close": IslandDoc(
        "(statement) the ':' closing a for @bindings header",
        "The end of a `for @bindings` header. It is mapped on its own "
        "because the header is rewritten in two pieces, around the iterable "
        "that stays verbatim Python.",
        _BINDINGS, "for-bindings-in-iter-the-loop-that-carries-them"),

    # -- graphs and the current graph ---------------------------------------

    "graph": IslandDoc(
        "(expression) g{ ... } -> Graph",
        "Builds an RDF graph from Turtle written in place. `{expr}` "
        "interpolates a Python value in term position, and each occurrence "
        "is evaluated once. The braces are an expression, so a `g{ }` goes "
        "anywhere a value goes — a default argument, a comprehension, a "
        "return.",
        _GRAPHS, "turtle-inside-the-braces"),

    "addto": IslandDoc(
        "(statement) +{ ... } [ (GRAPH) ]",
        "Adds the triples to the current graph. `?name` takes its value from "
        "the current bindings, and a triple with an unbound variable is "
        "dropped rather than written half-way. A trailing `(g)` names "
        "another receiver.",
        _CURRENT, "and-write-to-it"),

    "removefrom": IslandDoc(
        "(statement) -{ ... } [ (GRAPH) ]",
        "Removes from the current graph every triple matching the pattern. "
        "An unbound variable is a wildcard here, not a hole: this is a "
        "SPARQL `DELETE WHERE`, not a list of triples to subtract.",
        _CURRENT, "and-write-to-it"),

    # -- reading ------------------------------------------------------------

    "match": IslandDoc(
        "(expression) m{ ... } -> Solutions",
        "Matches a basic graph pattern against the current graph, lazily. "
        "Iterating yields a bare term when one variable is projected and a "
        "tuple otherwise; `.one()`, `.first()`, `.count()` and `bool()` are "
        "the usual reductions. A `(graph)` suffix names another source.",
        _QUERY, "m-match-a-basic-graph-pattern"),

    "sparql": IslandDoc(
        "(expression) s{ ... } -> Query",
        "A SPARQL query or update, parsed when the file is transpiled rather "
        "than at run time. `{expr}` in term position becomes an initial "
        "binding — never string pasting, so nothing here can be injected. "
        "Call it on a graph to run it; `.execute()` runs an update.",
        _QUERY, "s-a-sparql-query"),

    # -- terms --------------------------------------------------------------

    "iri": IslandDoc(
        "(term) <IRI> -> URIRef",
        "An absolute IRI, or a relative one resolved against the `@base` in "
        "scope.",
        _TERMS, "iris"),

    "pname": IslandDoc(
        "(term) ex:local -> URIRef",
        "A prefixed name: the local part is appended to the IRI bound to "
        "`ex:`. Turtle's character set applies inside an island, so "
        "`o-pizza:topping` and `ex:café` are names here although neither is "
        "a legal Python expression. `ex:{expr}` computes the local part.",
        _TERMS, "prefixed-names-exlocal"),

    "literal": IslandDoc(
        "(term) \"...\"@lang | \"...\"^^dt -> Literal",
        "An RDF literal carrying a language tag or a datatype. The quoted "
        "part may be an f-string, and `{expr}` may supply the datatype "
        "itself.",
        _TERMS, "rdf-literals-lang-dt"),

    "var": IslandDoc(
        "(term) ?name | $name -> Variable",
        "A SPARQL variable. In a pattern it is what gets matched and "
        "projected; in `g{ }` or `+{ }` it takes its value from the current "
        "bindings, and leaves the triple out when it has none.",
        _TERMS, "variables-name-name"),

    "firi": IslandDoc(
        "(term) f<...{expr}...> -> URIRef",
        "A formatted IRI: the braces interpolate as in an f-string, the "
        "result is percent-encoded and then resolved against `@base`. "
        "Encoding first is what keeps a space or a slash in a value from "
        "changing the IRI's structure.",
        _TERMS, "formatted-iris-f"),

    "fnode": IslandDoc(
        "(term) f{expr} | ?{expr} -> Node",
        "Coerces any Python value into an RDF term, by the coercion policy "
        "in scope. Two spellings of one operation: `?{ }` reads better in "
        "term position, `f{ }` beside `f<...>`.",
        _TERMS, "formatted-nodes-fexpr-expr"),

    "bnode": IslandDoc(
        "(term) _:{expr} -> BNode",
        "A blank node whose identity is its data: the same value gives the "
        "same node anywhere in the program, so two rows that share a key "
        "join without inventing an IRI for them.",
        _GRAPHS, "data-keyed-blank-nodes-_expr"),

    # -- deferred evaluation ------------------------------------------------

    "enode": IslandDoc(
        "(expression) e{ ... } -> Expr",
        "A deferred SPARQL expression. It is not evaluated where it is "
        "written, but against the bindings in force when the island holding "
        "it is instantiated — once per row of a `for @bindings` loop. "
        "`{python}` holes are evaluated where they are written.",
        _BINDINGS, "e-in-term-position"),

    "eiri": IslandDoc(
        "(expression) e<...{?var}...> -> Expr",
        "A deferred IRI: `f<...>`'s interpolation, except that the holes are "
        "SPARQL expressions re-evaluated for each set of bindings.",
        _SPARQL_EXPR, "deferred-iris-e"),
}


def get(kind):
    """The entry for an island kind, `island:` prefix optional; None if the
    kind is unknown — a hover must degrade, never raise."""
    if kind.startswith("island:"):
        kind = kind[len("island:"):]
    return ISLANDS.get(kind)
