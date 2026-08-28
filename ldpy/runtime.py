"""Runtime Linked-Data Python v2.

Le code généré par le transpileur importe ce module sous l'alias réservé
`_ldpy_` et n'utilise QUE cette façade — jamais rdflib directement. rdflib est
le backend par défaut ; la façade permet un backend alternatif (urdflib /
implémentation MicroPython) sans changer le code généré.

Les choix d'émission et de runtime sont expliqués dans docs/explanation/.
"""

import itertools

import rdflib
from rdflib import RDF, BNode, Literal, Variable, Namespace
from rdflib.term import Node

_URI_CACHE = {}


def URIRef(value, base=None):
    """rdflib.URIRef avec cache (clé = la chaîne). Les IRI émises par le
    transpileur sont des CONSTANTES du programme : sans cache, chaque tour de
    boucle sur un g{...} les reconstruisait (voir OPTIMIZATION.md). Le
    cache est borné par le texte des programmes ; garde-fou à 1M entrées pour
    les usages dynamiques via l'API."""
    if base is not None:
        return rdflib.URIRef(value, base)
    u = _URI_CACHE.get(value)
    if u is None:
        if len(_URI_CACHE) > 1_000_000:
            return rdflib.URIRef(value)
        u = _URI_CACHE.setdefault(value, rdflib.URIRef(value))
    return u

try:
    from urllib.parse import urljoin as _urljoin
except ImportError:  # MicroPython
    def _urljoin(base, rel):
        return base + rel

import re
_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:")

__all__ = [
    "RDF", "URIRef", "BNode", "Literal", "Variable", "Namespace",
    "node", "bn", "slot", "firi", "bnode", "dtype", "graph", "instantiateBGP",
    "sparql",
]


def __getattr__(name):
    """Charge ldpy.sparql à la demande (évite un import circulaire :
    sparql importe node() d'ici)."""
    if name == "sparql":
        from ldpy import sparql as _s
        globals()["sparql"] = _s
        return _s
    raise AttributeError(name)


class bn:
    """Placeholder de nœud anonyme dans un appel graph().

    L'indice est déterministe (position syntaxique dans le g{...} source) ;
    graph() crée un BNode frais par indice À CHAQUE évaluation. Les
    instances, immuables, sont mises en pool (une par indice)."""

    __slots__ = ("index",)
    _pool = {}

    def __new__(cls, index):
        inst = cls._pool.get(index)
        if inst is None:
            inst = super().__new__(cls)
            object.__setattr__(inst, "index", index)
            cls._pool[index] = inst
        return inst

    def __init__(self, index):
        pass

    def __repr__(self):
        return "bn(%d)" % self.index


class slot:
    """Terme partage par plusieurs triplets d'un meme g{...}.

    Un terme issu d'une interpolation (`ex:{expr}`, `f<...{expr}...>`, `{expr}`)
    qui sert de sujet a plusieurs triplets ne doit etre evalue QU'UNE FOIS :
    l'expression est emise a sa premiere occurrence, `slot(i)` la rappelle
    ensuite. Voir docs/explanation/emission-and-semantics.md."""

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
    ``_:{expr}`` .

    - un BNode passe tel quel ;
    - une chaîne qui est une étiquette sûre (lettres/chiffres/_/-) devient
      l'étiquette elle-même : ``_:{key}`` == BNode(key) ;
    - tout le reste — tuples notamment — est encodé canoniquement puis haché
      (``_:{(fname, lname)}`` ne
      collisionne pas avec ``_:{fname + lname}``, et l'étiquette produite
      reste sérialisable en N-Triples).

    À la différence de ``_:label`` (frais à chaque évaluation, portée
    l'îlot), ``_:{expr}`` désigne LE MÊME nœud partout où la valeur est
    égale — c'est l'idiome de déduplication et de jointure par bnode de
    R2RML (cas RMLTC0012a/b)."""
    if isinstance(value, BNode):
        return value
    if isinstance(value, str) and _BNODE_SAFE.match(value):
        return _bnode_cached(value)
    if isinstance(value, tuple):
        canon = "\x1f".join("%d:%s" % (len(str(p)), p) for p in value)
    else:
        canon = "%s:%r" % (type(value).__name__, value)
    import hashlib
    return _bnode_cached("b" + hashlib.md5(canon.encode("utf-8")).hexdigest())


def _bnode_cached(label, _cache={}):
    """Réutilise l'objet BNode existant pour une étiquette déjà vue (les
    charges de déduplication repassent sans cesse sur les mêmes clés)."""
    b = _cache.get(label)
    if b is None:
        if len(_cache) > 1_000_000:
            return BNode(label)
        b = _cache.setdefault(label, BNode(label))
    return b


_PASSTHROUGH = frozenset((rdflib.URIRef, Literal, BNode, Variable, bn))


def node(value):
    """Coercition d'une valeur Python en terme RDF (fnode / interpolations).
    Dispatch sur le type exact d'abord : le chemin isinstance/ABC de rdflib
    dominait le profil de matérialisation (voir OPTIMIZATION.md)."""
    if type(value) in _PASSTHROUGH:
        return value
    if isinstance(value, (Node, bn)):
        return value
    return Literal(value)


def dtype(value):
    """Coercition d'une valeur en IRI de type de donnée ({expr} après '^^').

    Un datatype est TOUJOURS un IRI : contrairement à node(), une chaîne est
    donc lue comme un IRI et non comme un littéral. Accepte aussi un objet
    exposant l'IRI par str() (URIRef, terme de DefinedNamespace)."""
    if type(value) is rdflib.URIRef:
        return value
    if isinstance(value, str):
        return URIRef(value)
    return URIRef(str(value))


def firi(*parts, base=None):
    """IRI formatée : concatène str(part) puis résout contre base si relative."""
    iri = "".join(p if isinstance(p, str) else str(p) for p in parts)
    if base and not _SCHEME_RE.match(iri):
        iri = _urljoin(base, iri)
    return URIRef(iri)


_graph_ids = itertools.count()
_NM_CACHE = {}


def _nm_for(namespaces):
    """NamespaceManager COSMÉTIQUE partagé pour un état donné du dict
    __namespaces__ : lier les préfixes coûte ~100x la création du graphe,
    et un g{...} évalué dans une boucle paie ce prix à chaque tour
    (voir OPTIMIZATION.md). Le manager est mis en cache et rattaché aux
    graphes produits — même motif de partage qu'instantiateBGP. Le cache est
    invalidé par instantané du contenu (l'identité seule ne suffit pas :
    portée par bloc, portée par bloc)."""
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


class _EmittedGraph(rdflib.Graph):
    """Graphe émis par g{...}, à matérialisation PARESSEUSE.

    Les triplets attendent dans une liste ; le store n'est peuplé qu'au
    premier accès réel. rdflib lit son stockage par l'attribut privé
    ``_Graph__store`` : une PROPRIÉTÉ du même nom (data descriptor, donc
    prioritaire sur l'attribut d'instance) est l'unique point de passage —
    tout accès interne de rdflib matérialise d'abord. Mais ``__iter__``
    sert la liste SANS matérialiser : ``cible += g{...}`` transfère alors
    les triplets directement — UNE insertion de store au lieu de deux
    (goulot mesuré : la moitié du coût de matérialisation par lignes)."""

    __slots__ = ("_real_store", "_pending")

    def __init__(self, *args, **kw):
        self._real_store = None
        self._pending = None
        super().__init__(*args, **kw)

    @property
    def _Graph__store(self):
        pending = self._pending
        if pending:
            self._pending = None
            self._real_store.addN(
                (s, p, o, self) for s, p, o in dict.fromkeys(pending))
        return self._real_store

    @_Graph__store.setter
    def _Graph__store(self, store):
        self._real_store = store

    def __iter__(self):
        pending = self._pending
        if pending is not None:
            return iter(dict.fromkeys(pending))
        return super().__iter__()

    def __len__(self):
        pending = self._pending
        if pending is not None:
            return len(dict.fromkeys(pending))
        return super().__len__()

    def _merged(self, left, right):
        """Nouveau graphe paresseux contenant left puis right (listes)."""
        g = _EmittedGraph(base=self.base,
                          identifier=rdflib.URIRef("urn:x-ldpy:g%d"
                                                   % next(_graph_ids)))
        nm = self._Graph__namespace_manager
        if nm is not None:
            g.namespace_manager = nm
        g._pending = left + right
        return g

    def __add__(self, other):
        """g1 + g2 paresseux : concatène les listes en attente, sans store.

        L'addition compositionnelle (patrons qui retournent des sommes de
        g{...}) devient O(total) au lieu de O(n²) en insertions de store ;
        la déduplication (sémantique d'union) reste assurée au flush."""
        pending = self._pending
        if pending is not None and isinstance(other, rdflib.Graph):
            if type(other) is _EmittedGraph and other._pending is not None:
                return self._merged(pending, other._pending)
            return self._merged(pending, list(other))
        return super().__add__(other)

    def __radd__(self, other):
        """Graph() + g{...} (et donc sum(...)) sans matérialisation."""
        pending = self._pending
        if pending is not None and isinstance(other, rdflib.Graph):
            return self._merged(list(other), pending)
        return NotImplemented


def graph(namespaces, base, *triples):
    """Construit un rdflib.Graph (sous-type paresseux) à partir de triplets
    aplatis.

    namespaces : dict prefix -> Namespace (liaisons de sérialisation,
    partagées via _nm_for) ; base : IRI de base lexicale (str ou None) ;
    triples : tuples (s, p, o) pouvant contenir des placeholders bn(i)."""
    g = _EmittedGraph(base=base,
                      identifier=rdflib.URIRef("urn:x-ldpy:g%d"
                                               % next(_graph_ids)))
    nm = _nm_for(namespaces)
    if nm is not None:
        g.namespace_manager = nm
    bnodes = {}
    slots = {}

    def _term(t):
        tt = type(t)
        if tt in _PASSTHROUGH:
            if tt is bn:
                b = bnodes.get(t.index)
                if b is None:
                    b = bnodes[t.index] = BNode()
                return b
            return t
        if tt is slot:
            if t.bound:
                slots[t.index] = node(t.value)
            return slots[t.index]
        return node(t)

    g._pending = [(_term(s), _term(p), _term(o)) for s, p, o in triples]
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
