"""Runtime Linked-Data Python v2.

Le code généré par le transpileur importe ce module sous l'alias réservé
`_ldpy_` et n'utilise QUE cette façade — jamais rdflib directement. rdflib est
le backend par défaut ; la façade permet un backend alternatif (urdflib /
implémentation MicroPython) sans changer le code généré.

Voir DESIGN_CHOICES/ldpy/003 (émission) et 008 (runtime).
"""

import rdflib
from rdflib import RDF, URIRef, BNode, Literal, Variable, Namespace
from rdflib.term import Node

try:
    from urllib.parse import urljoin as _urljoin
except ImportError:  # MicroPython
    def _urljoin(base, rel):
        return base + rel

import re
_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:")

__all__ = [
    "RDF", "URIRef", "BNode", "Literal", "Variable", "Namespace",
    "node", "bn", "slot", "firi", "bnode", "graph", "instantiateBGP",
]


class bn:
    """Placeholder de nœud anonyme dans un appel graph().

    L'indice est déterministe (position syntaxique dans le g{...} source) ;
    graph() crée un BNode frais par indice À CHAQUE évaluation."""

    __slots__ = ("index",)

    def __init__(self, index):
        self.index = index

    def __repr__(self):
        return "bn(%d)" % self.index


class slot:
    """Terme partage par plusieurs triplets d'un meme g{...}.

    Un terme issu d'une interpolation (`ex:{expr}`, `f<...{expr}...>`, `{expr}`)
    qui sert de sujet a plusieurs triplets ne doit etre evalue QU'UNE FOIS :
    l'expression est emise a sa premiere occurrence, `slot(i)` la rappelle
    ensuite. Voir DESIGN_CHOICES/ldpy/003."""

    __slots__ = ("index", "value", "bound")

    def __init__(self, index, *value):
        self.index = index
        self.bound = bool(value)
        self.value = value[0] if value else None

    def __repr__(self):
        return "slot(%d)" % self.index


_BNODE_SAFE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_\-]*\Z")


def bnode(value):
    """Nœud anonyme à IDENTITÉ DÉTERMINISTE issue des données : l'îlot
    ``_:{expr}`` (fiche 003, révision).

    - un BNode passe tel quel ;
    - une chaîne qui est une étiquette sûre (lettres/chiffres/_/-) devient
      l'étiquette elle-même : ``_:{key}`` == BNode(key) ;
    - tout le reste — tuples notamment — est encodé canoniquement puis haché
      (question de Maxime sur les collisions : ``_:{(fname, lname)}`` ne
      collisionne pas avec ``_:{fname + lname}``, et l'étiquette produite
      reste sérialisable en N-Triples).

    À la différence de ``_:label`` (frais à chaque évaluation, portée
    l'îlot), ``_:{expr}`` désigne LE MÊME nœud partout où la valeur est
    égale — c'est l'idiome de déduplication et de jointure par bnode de
    R2RML (cas RMLTC0012a/b)."""
    if isinstance(value, BNode):
        return value
    if isinstance(value, str) and _BNODE_SAFE.match(value):
        return BNode(value)
    if isinstance(value, tuple):
        canon = "\x1f".join("%d:%s" % (len(str(p)), p) for p in value)
    else:
        canon = "%s:%r" % (type(value).__name__, value)
    import hashlib
    return BNode("b" + hashlib.md5(canon.encode("utf-8")).hexdigest())


def node(value):
    """Coercition d'une valeur Python en terme RDF (fnode / interpolations)."""
    if isinstance(value, (Node, bn)):
        return value
    return Literal(value)


def firi(*parts, base=None):
    """IRI formatée : concatène str(part) puis résout contre base si relative."""
    iri = "".join(p if isinstance(p, str) else str(p) for p in parts)
    if base and not _SCHEME_RE.match(iri):
        iri = _urljoin(base, iri)
    return URIRef(iri)


_NM_CACHE = {}


def _nm_for(namespaces):
    """NamespaceManager COSMÉTIQUE partagé pour un état donné du dict
    __namespaces__ : lier les préfixes coûte ~100x la création du graphe,
    et un g{...} évalué dans une boucle paie ce prix à chaque tour
    (constat de l'étude KGC). Le manager est mis en cache et rattaché aux
    graphes produits — même motif de partage qu'instantiateBGP. Le cache est
    invalidé par instantané du contenu (l'identité seule ne suffit pas :
    portée par bloc, fiche 004)."""
    if not namespaces:
        return None
    key = id(namespaces)
    snap = tuple(sorted((p, str(u)) for p, u in namespaces.items()))
    hit = _NM_CACHE.get(key)
    if hit is not None and hit[0] == snap:
        return hit[1]
    holder = rdflib.Graph()
    nm = holder.namespace_manager
    for prefix, ns in namespaces.items():
        nm.bind(prefix, ns, replace=True)
    _NM_CACHE[key] = (snap, nm)
    return nm


def graph(namespaces, base, *triples):
    """Construit un rdflib.Graph à partir de triplets aplatis.

    namespaces : dict prefix -> Namespace (liaisons de sérialisation,
    partagées via _nm_for) ; base : IRI de base lexicale (str ou None) ;
    triples : tuples (s, p, o) pouvant contenir des placeholders bn(i)."""
    g = rdflib.Graph(base=base)
    nm = _nm_for(namespaces)
    if nm is not None:
        g.namespace_manager = nm
    bnodes = {}
    slots = {}

    def _term(t):
        if isinstance(t, slot):
            if t.bound:
                slots[t.index] = node(t.value)
            return slots[t.index]
        if isinstance(t, bn):
            if t.index not in bnodes:
                bnodes[t.index] = BNode()
            return bnodes[t.index]
        return node(t)

    for s, p, o in triples:
        g.add((_term(s), _term(p), _term(o)))
    return g


def instantiateBGP(input, solutionMappings, initialGraph=None):
    """Instancie un patron de graphe (BGP) avec des solution mappings.

    Reprise de v1 (ldpy/ldpy.py), inchangé fonctionnellement."""
    if initialGraph is None:
        initialGraph = rdflib.Graph(base=input.base)
    initialGraph.namespace_manager = input.namespace_manager
    if solutionMappings is None:
        return initialGraph
    if isinstance(solutionMappings, dict):
        solutionMappings = [solutionMappings]
    if not isinstance(solutionMappings, list):
        raise AssertionError(
            "solutionMappings doit être un dict ou une liste de dicts")

    def _instantiate(t, sm, bm):
        if isinstance(t, Variable):
            if t in sm:
                value = sm[t]
                if value is None:
                    return None
                if not isinstance(value, Node):
                    value = Literal(value)
                return value
            return None
        if isinstance(t, BNode):
            if t not in bm:
                bm[t] = BNode()
            return bm[t]
        return t

    for sm in solutionMappings:
        bm = {}
        for s, p, o in input:
            s2 = _instantiate(s, sm, bm)
            p2 = _instantiate(p, sm, bm)
            o2 = _instantiate(o, sm, bm)
            if s2 is not None and p2 is not None and o2 is not None:
                initialGraph.add((s2, p2, o2))
    return initialGraph
