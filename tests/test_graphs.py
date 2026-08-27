"""Graphes g{ ... } : construction, bnodes, collections, imbrications."""

from rdflib import Graph, URIRef, Literal, Variable, BNode, RDF
from rdflib.compare import isomorphic


def ttl(text):
    return Graph().parse(data=text, format="turtle")


EX = "http://example.org/ns#"


def test_empty_graph(run):
    g, _ = run("g = g{ }\n")
    assert isinstance(g["g"], Graph)
    assert len(g["g"]) == 0


def test_simple_triple(run, prefixes):
    g, _ = run(prefixes + "gr = g{ ex:s ex:p ex:o }\n")
    assert set(g["gr"]) == {(URIRef(EX + "s"), URIRef(EX + "p"), URIRef(EX + "o"))}


def test_a_shortcut_and_semicolon_comma(run, prefixes):
    g, _ = run(prefixes +
               'gr = g{ ex:s a ex:C ; ex:p "x", "y" }\n')
    expected = ttl('@prefix ex: <http://example.org/ns#> . '
                   'ex:s a ex:C ; ex:p "x", "y" .')
    assert isomorphic(g["gr"], expected)


def test_dot_separated_triples(run, prefixes):
    g, _ = run(prefixes + "gr = g{ ex:a ex:p 1 . ex:b ex:p 2 }\n")
    expected = ttl('@prefix ex: <http://example.org/ns#> . '
                   'ex:a ex:p 1 . ex:b ex:p 2 .')
    assert isomorphic(g["gr"], expected)


def test_multiline_graph(run, prefixes):
    src = prefixes + """\
gr = g{ ex:s a ex:C ;
        ex:p 1 ;
        ex:q "deux" }
after = 42
"""
    g, _ = run(src)
    expected = ttl('@prefix ex: <http://example.org/ns#> . '
                   'ex:s a ex:C ; ex:p 1 ; ex:q "deux" .')
    assert isomorphic(g["gr"], expected)
    assert g["after"] == 42


def test_anon_bnode_subject_and_nested(run, prefixes):
    g, _ = run(prefixes + "gr = g{ [ ex:p 1 ] ex:b [ ex:s [ ex:p 2 ]] }\n")
    expected = ttl('@prefix ex: <http://example.org/ns#> . '
                   '[ ex:p 1 ] ex:b [ ex:s [ ex:p 2 ]] .')
    assert isomorphic(g["gr"], expected)


def test_empty_anon(run, prefixes):
    g, _ = run(prefixes + "gr = g{ [] a ex:C }\n")
    expected = ttl('@prefix ex: <http://example.org/ns#> . [] a ex:C .')
    assert isomorphic(g["gr"], expected)


def test_labeled_bnodes_shared_within_graph(run, prefixes):
    g, _ = run(prefixes + "gr = g{ _:b ex:p 1 . _:b ex:q 2 }\n")
    subjects = {s for s, _, _ in g["gr"]}
    assert len(subjects) == 1
    assert isinstance(next(iter(subjects)), BNode)


def test_collections(run, prefixes):
    g, _ = run(prefixes + "gr = g{ <http://e/z> ex:b ( 1 2 (3 4 ) ( 5 (8) ) ) }\n")
    expected = ttl('@prefix ex: <http://example.org/ns#> . '
                   '<http://e/z> ex:b ( 1 2 (3 4) (5 (8)) ) .')
    assert isomorphic(g["gr"], expected)


def test_empty_collection_is_nil(run, prefixes):
    g, _ = run(prefixes + "gr = g{ ex:s ex:p () }\n")
    assert (URIRef(EX + "s"), URIRef(EX + "p"), RDF.nil) in g["gr"]


def test_variables_in_graph(run, prefixes):
    g, _ = run(prefixes + "gr = g{ ?var a ex:Obs ; ex:r ?result }\n")
    assert (Variable("var"), RDF.type, URIRef(EX + "Obs")) in g["gr"]
    assert (Variable("var"), URIRef(EX + "r"), Variable("result")) in g["gr"]


def test_interpolation_in_graph(run, prefixes):
    src = prefixes + """\
valeur = 21.5
capteur = "c1"
gr = g{ ex:{capteur} a ex:Sensor ; ex:val {valeur} }
"""
    g, _ = run(src)
    assert (URIRef(EX + "c1"), RDF.type, URIRef(EX + "Sensor")) in g["gr"]
    assert (URIRef(EX + "c1"), URIRef(EX + "val"), Literal(21.5)) in g["gr"]


def test_fnode_and_qnode_in_graph(run, prefixes):
    src = prefixes + """\
test = True
x = <http://e/hello>
gr = g{ [] a f{ x if test else ex:World } ; ex:n ?{ 4+1 } }
"""
    g, _ = run(src)
    assert (None, RDF.type, URIRef("http://e/hello")) in g["gr"]
    assert (None, URIRef(EX + "n"), Literal(5)) in g["gr"]


def test_literals_in_graph(run, prefixes):
    src = prefixes + \
        'gr = g{ ex:s ex:a "brut" ; ex:b "typé"^^xsd:string ; ' \
        'ex:c "tagué"@fr ; ex:d -5 ; ex:e 2.5 ; ex:f true ; ex:g False }\n'
    g, _ = run(src)
    vals = {o for _, _, o in g["gr"]}
    assert Literal("brut") in vals
    assert Literal("typé", datatype=URIRef(
        "http://www.w3.org/2001/XMLSchema#string")) in vals
    assert Literal("tagué", lang="fr") in vals
    assert Literal(-5) in vals
    assert Literal(2.5) in vals
    assert Literal(True) in vals
    assert Literal(False) in vals


def test_relative_iris_in_graph(run):
    src = "@base <http://example.org/data/> .\ngr = g{ <z> <p> <#f> }\n"
    g, _ = run(src)
    assert (URIRef("http://example.org/data/z"),
            URIRef("http://example.org/data/p"),
            URIRef("http://example.org/data/#f")) in g["gr"]


def test_graph_method_chaining(run, prefixes):
    g, _ = run(prefixes + "n = len(g{ ex:a ex:b ex:c })\n")
    assert g["n"] == 1


def test_graph_in_default_arg_and_lambda(run, prefixes):
    src = prefixes + """\
def f(gr=g{ [] ex:p 1 }):
    return gr
mk = lambda: g{ ex:s ex:p 2 }
r1 = f()
r2 = mk()
"""
    g, _ = run(src)
    assert len(g["r1"]) == 1
    assert (URIRef(EX + "s"), URIRef(EX + "p"), Literal(2)) in g["r2"]


def test_fresh_bnodes_per_evaluation(run, prefixes):
    src = prefixes + """\
def mk():
    return g{ [] ex:p 1 }
g1 = mk()
g2 = mk()
s1 = next(iter(g1))[0]
s2 = next(iter(g2))[0]
"""
    g, _ = run(src)
    assert g["s1"] != g["s2"]


def test_comment_inside_graph(run, prefixes):
    src = prefixes + """\
gr = g{ ex:s ex:p 1 ;  # un commentaire
        ex:q 2 }
"""
    g, _ = run(src)
    assert len(g["gr"]) == 2


def test_namespace_bindings_on_graph(run, prefixes):
    g, _ = run(prefixes + "gr = g{ ex:s ex:p 1 }\n")
    nss = dict(g["gr"].namespace_manager.namespaces())
    assert str(nss.get("ex")) == EX


def test_nested_graph_via_fnode(run, prefixes):
    g, _ = run(prefixes + "gr = g{ ex:s ex:n ?{ len(g{ ex:a ex:b 1 }) } }\n")
    assert (URIRef(EX + "s"), URIRef(EX + "n"), Literal(1)) in g["gr"]


def test_namespace_manager_shared_and_invalidated(run, prefixes):
    """Optimisation issue de l'étude KGC : le NamespaceManager cosmétique est
    partagé entre les graphes d'un même état de __namespaces__ (lier les
    préfixes coûtait ~100x la création du graphe, payé à chaque tour de
    boucle), et invalidé quand la table change (portée par bloc)."""
    src = prefixes + """\
gs = [ g{ ex:s ex:p {i} } for i in range(50) ]
nm_ids = {id(x.namespace_manager) for x in gs}
@prefix zz: <http://zz/> .
g2 = g{ zz:a zz:b 1 }
has_zz = dict(g2.namespace_manager.namespaces()).get("zz")
"""
    g, _ = run(src)
    assert len(g["nm_ids"]) == 1                  # partagé
    assert str(g["has_zz"]) == "http://zz/"       # invalidé puis reconstruit


def test_interpolated_bnode_deterministic_identity(run, prefixes):
    """_:{expr} : identité déterministe issue des données — l'idiome de
    déduplication/jointure de R2RML (cas RMLTC0012a/b de l'étude KGC)."""
    src = prefixes + """\
rows = [("Bob", "Smith", "30"), ("Sue", "Jones", "20"), ("Bob", "Smith", "30")]
gr = Graph = None
from rdflib import Graph
gr = Graph()
for fname, lname, amount in rows:
    gr += g{ _:{fname + lname + amount} ex:amount {amount} }
subjects = {s for s, _, _ in gr}
"""
    g, _ = run(src)
    assert len(g["subjects"]) == 2          # doublon fusionné
    assert len(g["gr"]) == 2


def test_interpolated_bnode_tuple_avoids_collision(run, prefixes):
    """Question de Maxime : un tuple comme clé — encodage canonique haché,
    pas de collision entre ("Bob","bySmith") et ("Bobby","Smith"), et
    l'étiquette produite reste sérialisable."""
    src = prefixes + """\
a = g{ _:{("Bob", "bySmith")} ex:p 1 }
b = g{ _:{("Bobby", "Smith")} ex:p 1 }
c = g{ _:{("Bob", "bySmith")} ex:q 2 }
sa = next(iter(a))[0]
sb = next(iter(b))[0]
sc = next(iter(c))[0]
nt = (a + c).serialize(format="nt")
"""
    g, _ = run(src)
    assert g["sa"] != g["sb"]               # pas de collision
    assert g["sa"] == g["sc"]               # déterministe
    assert "_:b" in g["nt"]                 # étiquette N-Triples valide


def test_interpolated_bnode_vs_static_label(run, prefixes):
    """_:b statique = frais à chaque évaluation (portée l'îlot) ;
    _:{'b'} = identité stable inter-évaluations. Les deux coexistent."""
    src = prefixes + """\
f1 = g{ _:b ex:p 1 }
f2 = g{ _:b ex:p 1 }
s1 = g{ _:{'b'} ex:p 1 }
s2 = g{ _:{'b'} ex:p 1 }
fresh = next(iter(f1))[0] != next(iter(f2))[0]
stable = next(iter(s1))[0] == next(iter(s2))[0]
"""
    g, _ = run(src)
    assert g["fresh"] and g["stable"]


def test_interpolated_bnode_shared_subject_single_eval(run, prefixes):
    src = prefixes + """\
calls = []
def key():
    calls.append(1)
    return "k1"
gr = g{ _:{key()} ex:p 1 ; ex:q 2 }
"""
    g, _ = run(src)
    assert len(g["calls"]) == 1
    assert len({s for s, _, _ in g["gr"]}) == 1


def test_interp_language_suffix(run, prefixes):
    """{expr}@lang — accepté par Maxime (friction RMLTC0015a)."""
    src = prefixes + """\
name = "Irlande"
gr = g{ ex:IE ex:label {name}@fr, {name.upper()}@fr-CA ; ex:n {name} }
"""
    g, _ = run(src)
    vals = {o for _, _, o in g["gr"]}
    assert Literal("Irlande", lang="fr") in vals
    assert Literal("IRLANDE", lang="fr-CA") in vals
    assert Literal("Irlande") in vals       # sans suffixe : node() inchangé


def test_interp_datatype_suffix(run, prefixes):
    src = prefixes + """\
v = "42"
gr = g{ ex:s ex:p {v}^^xsd:integer ; ex:q ?{v}^^<http://e/dt> }
"""
    g, _ = run(src)
    vals = {o for _, _, o in g["gr"]}
    assert Literal("42", datatype=URIRef(
        "http://www.w3.org/2001/XMLSchema#integer")) in vals
    assert Literal("42", datatype=URIRef("http://e/dt")) in vals


def test_matmul_with_spaces_still_python_in_expr(run, prefixes):
    """Le suffixe exige l'adjacence : '{expr} @ y' reste du Python (matmul
    DANS l'expression), et un @ SÉPARÉ après l'accolade est une erreur ldpy
    claire, pas un langtag silencieux."""
    src = prefixes + """\
class M:
    def __matmul__(self, other):
        return 7
gr = g{ ex:s ex:p {M() @ M()} }
"""
    g, _ = run(src)
    assert (None, None, Literal(7)) in g["gr"]


def test_emitted_graph_lazy_semantics(run, prefixes):
    """La matérialisation paresseuse des g{...} est invisible : itération
    dédupliquée, len ensembliste, requêtes, sérialisation, mutation après
    lecture — tout se comporte comme un Graph ordinaire."""
    src = prefixes + """\
gr = g{ ex:s ex:p 1 . ex:s ex:p 1 ; ex:q 2 }
n0 = len(gr)
l0 = len(list(gr))
member = (ex:s, ex:p, ?{1}) in gr
sparql = len(list(gr.query("SELECT ?o WHERE { ?s ?p ?o }")))
gr.add((ex:z, ex:p, ?{9}))
n1 = len(gr)
ttl = gr.serialize(format="turtle")
"""
    g, _ = run(src)
    assert g["n0"] == 2 and g["l0"] == 2       # dédupliqué partout
    assert g["member"] is True
    assert g["sparql"] == 2
    assert g["n1"] == 3
    assert "ex:q" in g["ttl"] or "q" in g["ttl"]


def test_emitted_graph_iadd_transfers_without_flush(run, prefixes):
    src = prefixes + """\
from rdflib import Graph
target = Graph()
for i in range(10):
    tmp = g{ ex:s{i} ex:p {i} }
    flushed_before = tmp._pending is None
    target += tmp
    still_lazy = tmp._pending is not None
n = len(target)
"""
    g, _ = run(src)
    assert g["n"] == 10
    assert g["flushed_before"] is False        # jamais matérialisé...
    assert g["still_lazy"] is True             # ...même après le +=
