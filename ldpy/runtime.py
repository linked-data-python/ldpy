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
    "pname", "new_graph", "add_to", "remove_from", "match", "prepared",
    "Bindings", "as_bindings_iter",
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


def pname(ns, *parts):
    """Nom préfixé dynamique (fiche 013) : concatène l'IRI du namespace
    (préfixe importé ou à IRI calculée) et la partie locale."""
    return rdflib.URIRef(
        str(ns) + "".join(p if isinstance(p, str) else str(p) for p in parts))


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


class Bindings(dict):
    """Binding courant (fiche 017) : un dict à clés str ou Variable
    (normalisées en str), valeurs coercées en termes RDF à l'affectation.
    Tout ce que Python sait faire sur un dict marche : b[?x] = v, update,
    del, **b, itération sur les clés."""

    def __init__(self, mapping=None):
        dict.__init__(self)
        if mapping is not None:
            if not hasattr(mapping, "items"):
                raise TypeError(
                    "Bindings attend un mapping, reçu %s"
                    % type(mapping).__name__)
            for k, v in mapping.items():
                self[k] = v

    def __setitem__(self, key, value):
        dict.__setitem__(self, str(key), node(value))

    def __getitem__(self, key):
        return dict.__getitem__(self, str(key))

    def __delitem__(self, key):
        dict.__delitem__(self, str(key))

    def __contains__(self, key):
        return dict.__contains__(self, str(key))

    def get(self, key, default=None):
        """dict.get, clé str ou Variable."""
        return dict.get(self, str(key), default)

    def update(self, other=(), **kw):
        """dict.update, en passant par la coercition de __setitem__."""
        items = other.items() if hasattr(other, "items") else other
        for k, v in items:
            self[k] = v
        for k, v in kw.items():
            self[k] = v


def as_bindings_iter(iterable):
    """'for @bindings in ...' (fiche 017) : chaque élément devient le
    binding courant du corps. Un m{ ... } livre ses solutions (variables
    anonymes exclues) ; tout autre itérable doit produire des mappings."""
    if isinstance(iterable, Match):
        for sm in iterable.solutions():
            b = Bindings()
            for k, v in sm.items():
                if not str(k).startswith("__bn"):
                    dict.__setitem__(b, str(k), v)      # déjà des termes
            yield b
        return
    for item in iterable:
        if isinstance(item, Bindings):
            yield item
        elif hasattr(item, "items"):
            yield Bindings(item)
        else:
            raise TypeError(
                "for @bindings in ... : l'itérable doit produire des "
                "mappings, reçu %s" % type(item).__name__)


_EXPR_CLASS = None


def _expr_class():
    """Classe Expression de ldpy.sparql, chargée à la demande (None si le
    module n'est pas disponible)."""
    global _EXPR_CLASS
    if _EXPR_CLASS is None:
        try:
            from ldpy.sparql import Expression
            _EXPR_CLASS = Expression
        except ImportError:
            _EXPR_CLASS = False
    return _EXPR_CLASS


def _bind_get(bindings, var):
    """Valeur d'une variable dans un mapping à clés str ou Variable ;
    None = non liée (convention d'instantiateBGP)."""
    v = bindings.get(var)
    if v is None:
        v = bindings.get(str(var))
    return v


def _materializer(bindings=None, keep_vars=True):
    """Fabrique le matérialiseur de termes des îlots (fiches 014/016/017).

    bn(i) -> BNode frais par évaluation (mémoïsé par indice) ; slot -> valeur
    partagée ; Variable -> valeur du binding si liée, sinon la Variable
    elle-même (keep_vars, régime gabarit) ou None (triplet à écarter)."""
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
            if tt is Variable:
                if bindings is not None:
                    v = _bind_get(bindings, t)
                    if v is not None:
                        return node(v)
                return t if keep_vars else None
            return t
        if tt is slot:
            if t.bound:
                slots[t.index] = node(t.value)
            return slots[t.index]
        cls = _expr_class()
        if cls and tt is cls:
            # e{ ... } en position de terme (fiches 007/017) : différé sans
            # binding, évalué contre le binding courant sinon — une erreur
            # SPARQL laisse le terme non lié, le triplet est écarté.
            if bindings is None:
                return t if keep_vars else None
            try:
                return node(t(bindings))
            except Exception:
                return None
        return node(t)

    return _term


def new_graph(namespaces, base, identifier=None):
    """Graphe créé par '@graph as g' (fiche 014) : un rdflib.Graph ordinaire,
    avec les liaisons de sérialisation des préfixes en portée."""
    g = rdflib.Graph(base=base, identifier=identifier)
    nm = _nm_for(namespaces)
    if nm is not None:
        g.namespace_manager = nm
    return g


def add_to(graph, *triples, bindings=None):
    """'+{ ... }' : instancie et ajoute au graphe courant (fiche 014).
    Un triplet dont un terme reste non lié est écarté — on ne peut pas
    écrire un terme inconnu."""
    term = _materializer(bindings, keep_vars=False)
    for s, p, o in triples:
        s2, p2, o2 = term(s), term(p), term(o)
        if s2 is not None and p2 is not None and o2 is not None:
            graph.add((s2, p2, o2))
    return graph


def remove_from(graph, *patterns, bindings=None):
    """'-{ ... }' : retrait du graphe courant (fiche 014). Une variable non
    liée est un joker (sémantique remove((s, p, None)) de rdflib) ; à
    plusieurs motifs partageant une variable, DELETE WHERE par appariement
    (fiche 016)."""
    has_vars = any(isinstance(x, (Variable, bn))
                   for tr in patterns for x in tr)
    if len(patterns) > 1 and has_vars:
        # DELETE WHERE : apparier le BGP (fiche 016) puis retirer les
        # triplets instanciés — collectés d'abord, le graphe ne doit pas
        # être modifié pendant l'appariement.
        prepared_pats, _ = _match_prepare(patterns, bindings)
        to_remove = set()
        for sm in Match(graph, patterns, (), bindings).solutions():
            for tr in prepared_pats:
                inst = tuple(sm.get(x) if isinstance(x, Variable) else x
                             for x in tr)
                if all(t is not None for t in inst):
                    to_remove.add(inst)
        for tr in to_remove:
            graph.remove(tr)
        return graph
    term = _materializer(bindings, keep_vars=True)
    for s, p, o in patterns:
        tr = tuple(None if isinstance(x, (Variable, bn)) else x
                   for x in (term(s), term(p), term(o)))
        graph.remove(tr)
    return graph


def graph(namespaces, base, *triples, bindings=None):
    """Construit un rdflib.Graph (sous-type paresseux) à partir de triplets
    aplatis.

    namespaces : dict prefix -> Namespace (liaisons de sérialisation,
    partagées via _nm_for) ; base : IRI de base lexicale (str ou None) ;
    triples : tuples (s, p, o) pouvant contenir des placeholders bn(i).
    Sans binding, un g{ } à variables ou à e{ } reste un gabarit ; avec le
    binding courant en portée, il est instancié (fiche 017) — un triplet
    dont un terme reste non lié est écarté."""
    g = _EmittedGraph(base=base,
                      identifier=rdflib.URIRef("urn:x-ldpy:g%d"
                                               % next(_graph_ids)))
    nm = _nm_for(namespaces)
    if nm is not None:
        g.namespace_manager = nm
    _term = _materializer(bindings, keep_vars=(bindings is None))
    if bindings is None:
        g._pending = [(_term(s), _term(p), _term(o)) for s, p, o in triples]
    else:
        g._pending = [tr for tr in
                      ((_term(s), _term(p), _term(o))
                       for s, p, o in triples)
                      if tr[0] is not None and tr[1] is not None
                      and tr[2] is not None]
    return g


# ---------------------------------------------------------------- m{ ... }

class Row(tuple):
    """Solution d'un m{ ... } d'arité >= 2 : tuple déballable, accès nommé
    (row.s) et indexé par variable (row[?v] ou row['v'])."""

    def __new__(cls, values, fields):
        r = tuple.__new__(cls, values)
        r._fields = fields
        return r

    def __getattr__(self, name):
        try:
            return self[self._fields.index(name)]
        except ValueError:
            raise AttributeError(name)

    def __getitem__(self, key):
        if isinstance(key, (str, Variable)):
            return tuple.__getitem__(self, self._fields.index(str(key)))
        return tuple.__getitem__(self, key)

    def __repr__(self):
        return "Row(%s)" % ", ".join(
            "%s=%r" % (f, tuple.__getitem__(self, i))
            for i, f in enumerate(self._fields))


def _match_prepare(patterns, bindings):
    """Motifs prêts à l'appariement : bn -> variable anonyme partagée par
    indice, slot -> valeur, variables liées par le binding -> terme."""
    init = {}
    if bindings:
        for k, v in bindings.items():
            init[Variable(str(k))] = node(v)
    out = []
    slots = {}
    for s, p, o in patterns:
        tr = []
        for t in (s, p, o):
            tt = type(t)
            if tt is bn:
                t = Variable("__bn%d" % t.index)
            elif tt is slot:
                if t.bound:
                    slots[t.index] = node(t.value)
                t = slots[t.index]
            if isinstance(t, Variable) and t in init:
                t = init[t]
            tr.append(t)
        out.append(tuple(tr))
    return out, init


class Match:
    """Valeur d'un îlot m{ ... } (fiche 016) : jointure par boucles
    imbriquées sur graph.triples(), dans l'ordre écrit — aucun moteur,
    aucune heuristique. Paresseux : itérer, tester ou first() n'apparie
    que le nécessaire."""

    __slots__ = ("graph", "patterns", "project", "bindings")

    def __init__(self, graph, patterns, project, bindings=None):
        self.graph = graph
        self.patterns = patterns
        self.project = project
        self.bindings = bindings

    def __call__(self, graph=None, bindings=None):
        return Match(self.graph if graph is None else graph,
                     self.patterns, self.project,
                     self.bindings if bindings is None else bindings)

    def solutions(self):
        """Générateur de solution mappings (Bindings variable -> terme),
        liaisons initiales incluses (projetées, fiche 019)."""
        if self.graph is None:
            raise RuntimeError(
                "m{ } sans graphe : déclarez '@graph ...' en portée, ou "
                "appliquez le motif à un graphe — m{ ... }(g)")
        patterns, init = _match_prepare(self.patterns, self.bindings)
        graph = self.graph

        def join(i, sm):
            if i == len(patterns):
                yield sm
                return
            pat = []
            var_pos = []
            for k, t in enumerate(patterns[i]):
                if isinstance(t, Variable):
                    v = sm.get(t)
                    if v is None:
                        var_pos.append((k, t))
                        v = None
                    pat.append(v)
                else:
                    pat.append(t)
            for found in graph.triples(tuple(pat)):
                sm2 = dict(sm)
                ok = True
                for k, var in var_pos:
                    val = found[k]
                    prev = sm2.get(var)
                    if prev is not None and prev != val:
                        ok = False
                        break
                    sm2[var] = val
                if ok:
                    yield from join(i + 1, sm2)

        yield from join(0, dict(init))

    def __iter__(self):
        proj = self.project
        if len(proj) == 1:
            v = Variable(proj[0])
            for sm in self.solutions():
                yield sm.get(v)
        else:
            vs = [Variable(x) for x in proj]
            for sm in self.solutions():
                yield Row((sm.get(x) for x in vs), list(proj))

    def __bool__(self):
        for _ in self.solutions():
            return True
        return False

    def first(self):
        """La première solution, ou None s'il n'y en a pas (~ g.value)."""
        for x in self:
            return x
        return None

    def one(self):
        """L'unique solution ; lève s'il y en a zéro ou plusieurs."""
        it = iter(self)
        try:
            first = next(it)
        except StopIteration:
            raise ValueError("m{ }.one() : aucune solution")
        for _ in it:
            raise ValueError("m{ }.one() : plusieurs solutions")
        return first

    def count(self):
        """Nombre de solutions — consomme l'appariement (len() échoue)."""
        n = 0
        for _ in self.solutions():
            n += 1
        return n

    def __repr__(self):
        return "m{ %d motif(s), projection %r }" % (
            len(self.patterns), tuple(self.project))


def match(graph, patterns, project, bindings=None):
    """Construit la valeur d'un îlot m{ ... } (fiche 016)."""
    return Match(graph, patterns, project, bindings)


# ---------------------------------------------------------------- s{ ... }

_SPARQL_CACHE = {}      # (texte, clé ns) -> requête préparée
_SPARQL_CACHE_MAX = 64  # borné ; écrit à la main (pas de lru_cache : fiche 008)


def _prepare_sparql(text, namespaces, update):
    key = (text, update, tuple(sorted((k, str(v))
                                      for k, v in namespaces.items())))
    hit = _SPARQL_CACHE.get(key)
    if hit is not None:
        return hit
    from rdflib.plugins.sparql import prepareQuery, prepareUpdate
    prep = (prepareUpdate if update else prepareQuery)(
        text, initNs=dict(namespaces))
    if len(_SPARQL_CACHE) >= _SPARQL_CACHE_MAX:
        _SPARQL_CACHE.pop(next(iter(_SPARQL_CACHE)))
    _SPARQL_CACHE[key] = prep
    return prep


class PreparedQuery:
    """Valeur d'un îlot s{ ... } (fiche 015) : requête préparée, paresseuse.

    L'itérer (ou la tester) l'exécute sur son graphe ; l'appeler la relie —
    suffixe d'appel de la fiche 019 : graphe d'abord, binding ensuite."""

    __slots__ = ("text", "interps", "namespaces", "base",
                 "graph", "bindings", "update")

    def __init__(self, text, interps, namespaces, base,
                 graph=None, bindings=None, update=False):
        self.text = text
        self.interps = interps
        self.namespaces = namespaces
        self.base = base
        self.graph = graph
        self.bindings = bindings
        self.update = update

    def __call__(self, graph=None, bindings=None):
        return PreparedQuery(self.text, self.interps, self.namespaces,
                             self.base,
                             graph if graph is not None else self.graph,
                             bindings if bindings is not None else self.bindings,
                             self.update)

    def _init_bindings(self):
        init = {}
        if self.bindings:
            for k, v in self.bindings.items():
                init[Variable(str(k))] = node(v)
        for name, value in self.interps:
            init[Variable(name)] = node(value)
        return init

    def _execute(self):
        if self.graph is None:
            raise RuntimeError(
                "s{ } sans graphe : déclarez '@graph ...' en portée, ou "
                "appliquez la requête à un graphe — s{ ... }(g)")
        prep = _prepare_sparql(self.text, self.namespaces, self.update)
        if self.update:
            return self.graph.update(prep, initBindings=self._init_bindings())
        return self.graph.query(prep, initBindings=self._init_bindings())

    def __iter__(self):
        return iter(self._execute())

    def __bool__(self):
        res = self._execute()
        if getattr(res, "type", None) == "ASK":
            return bool(res.askAnswer)
        return res is not None and bool(len(res))

    def __repr__(self):
        return "s{ %s }" % self.text


def prepared(text, interps, namespaces, base, graph=None, bindings=None,
             update=False):
    """Construit la valeur d'un îlot s{ ... } (fiche 015)."""
    return PreparedQuery(text, interps, namespaces, base,
                         graph, bindings, update)


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
