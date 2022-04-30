from typing import Union, Dict, List, Set
from rdflib import RDF, OWL, Graph, URIRef, BNode, Literal, Variable
from rdflib.term import Node

RDFTerm = Union[URIRef, BNode, Literal]
Term = Union[Variable, URIRef, BNode, Literal]
RDFInstanceMapping = Dict[BNode, RDFTerm]
SolutionMapping = Dict[Variable, RDFTerm]

def instantiateBGP(input:Graph, solutionMappings, initialGraph:Graph=None):
    if initialGraph == None:
        initialGraph=Graph(base=input.base)
    initialGraph.namespace_manager = input.namespace_manager
    if solutionMappings is None:
        return initialGraph
    if isinstance(solutionMappings, dict):
        solutionMappings = [solutionMappings]
    if not isinstance(solutionMappings, list):
        raise AssertionError("solutionMappings needs to be a dictionary, or list of dictionaries")
    def instantiateTerm(t:Term, solutionMapping:SolutionMapping, rdfInstanceMapping:RDFInstanceMapping):
        """If the input term is a variable, replace it by its value in the solution mapping. Return None if this variable is not mapped. If the input term is a blank node, replace it by its value in the RDF instance mapping. Create one if it is not mapped."""
        if isinstance(t, Variable):
            if t in set(solutionMapping):
                value = solutionMapping[t]
                if value == None:
                    return None
                if not isinstance(value, Node):
                    value = Literal(value)
                return value
            else:
                return None
        if isinstance(t, BNode):
            if t in set(rdfInstanceMapping):
                return rdfInstanceMapping[t]
            else:
                bnode = BNode()
                rdfInstanceMapping[t] = bnode
                return bnode
        return t            
    for solutionMapping in solutionMappings:
        rdfInstanceMapping={} # type: RDFInstanceMapping
        for s,p,o in input:
            s = instantiateTerm(s, solutionMapping, rdfInstanceMapping)
            p = instantiateTerm(p, solutionMapping, rdfInstanceMapping)
            o = instantiateTerm(o, solutionMapping, rdfInstanceMapping)
            if s and p and o:
                initialGraph.add((s, p, o))
    return initialGraph
