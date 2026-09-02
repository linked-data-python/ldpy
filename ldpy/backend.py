"""The RDF backend of the façade: rdflib on CPython, urdflib on MicroPython.

The generated code never touches rdflib: it goes through `ldpy.runtime`,
and `ldpy.runtime` takes its terms and graphs from HERE. So this module is
the one place that knows which library is underneath — and the contract a
backend must meet is exactly its public names (record urdflib/306 measures
them with `urdflib/tools/api_gap.py`).

Two backends:

* **rdflib**, whenever it imports — the default on CPython, and the only one
  with a SPARQL engine (`s{ }`);
* **urdflib**, the MicroPython C module of the linked-data-python
  organisation, when rdflib is absent. It has the terms and the graphs;
  `Namespace`, `RDF` and `XSD` are pure Python and provided here.

The two are not exclusive options of the same kind: the backend is chosen
by what is importable, and SPARQL queries are a capability of one backend.
`e{ }` expressions (ldpy.sparql) are pure Python over the terms, and run on
both.
"""

try:
    import rdflib as _lib
    from rdflib import RDF, XSD, BNode, Literal, Namespace, Variable
    from rdflib.term import Node
    URIRef = _lib.URIRef
    Graph = _lib.Graph
    NAME = "rdflib"
    HAS_SPARQL = True
    HAS_NAMESPACE_MANAGER = True
except ImportError:                                  # MicroPython
    import urdflib as _lib
    from urdflib import BNode, Literal, Node, URIRef, Variable, Graph
    NAME = "urdflib"
    HAS_SPARQL = False
    HAS_NAMESPACE_MANAGER = False

    class Namespace(str):
        """A namespace IRI whose attributes and items are terms — rdflib's
        Namespace, reduced to what the emitted code uses."""

        def __getattr__(self, name):
            if name.startswith("__"):
                raise AttributeError(name)
            return URIRef(self + name)

        def __getitem__(self, name):
            return URIRef(self + name)

        def term(self, name):
            return URIRef(self + name)

    RDF = Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")
    XSD = Namespace("http://www.w3.org/2001/XMLSchema#")


def new_graph(base=None, identifier=None):
    """A graph of the backend. rdflib's takes a base, urdflib's does not
    (a base is a lexical matter, resolved by the transpiler already)."""
    if NAME == "rdflib":
        return Graph(base=base, identifier=identifier)
    return Graph(identifier=identifier) if identifier is not None else Graph()


def bind_namespaces(graph, namespaces):
    """Give `graph` the serialisation prefixes of `namespaces` (a dict
    prefix -> namespace IRI). On rdflib the runtime shares a cached
    NamespaceManager instead (record ldpy/021); this is the plain path."""
    for prefix, ns in namespaces.items():
        graph.bind(prefix, str(ns))


def prepare_sparql(text, namespaces, update=False):
    """A prepared SPARQL query or update — rdflib's engine, or an error
    that says which backend is missing it."""
    if not HAS_SPARQL:
        raise RuntimeError(
            "s{ } needs a SPARQL engine, and the %s backend has none: "
            "transpile with target='micropython' to be told at build time, "
            "and use m{ } and e{ } on the device" % NAME)
    from rdflib.plugins.sparql import prepareQuery, prepareUpdate
    return (prepareUpdate if update else prepareQuery)(
        text, initNs=dict(namespaces))


__all__ = ["NAME", "HAS_SPARQL", "HAS_NAMESPACE_MANAGER",
           "URIRef", "BNode", "Literal", "Variable", "Node", "Graph",
           "Namespace", "RDF", "XSD",
           "new_graph", "bind_namespaces", "prepare_sparql"]
