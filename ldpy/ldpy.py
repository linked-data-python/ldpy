import os
import sys
import math

from typing import Union, Dict, List, Set
from rdflib import RDF, OWL, Graph, URIRef, BNode, Literal, Variable
from rdflib.term import Node

from antlr4 import InputStream, Token
from antlr4.error.ErrorListener import ErrorListener
from antlr4.error.DiagnosticErrorListener import DiagnosticErrorListener

from ideas import import_hook

from ldpy.rewriter import *
import ldpy


RDFTerm = Union[URIRef, BNode, Literal]
Term = Union[Variable, URIRef, BNode, Literal]
RDFInstanceMapping = Dict[BNode, RDFTerm]
SolutionMapping = Dict[Variable, RDFTerm]


class Config:
    def __init__(self):
        self.debug_ldpy = False
        self.debug_lexer = False
        self.debug_parser = False
        self.linemap = dict()
        self.namespaces = dict()

config = Config()

class MainErrorListener(ErrorListener):
    
    def __init__(self):
        self.errors = []
    
    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        self.errors.append("line " + str(line) + ":" + str(column) + " " + msg)

def parseTree(input_stream, filename="<none>", diagnose=False): 
    lexer = LDPythonLexer(input_stream)
    stream = MultiChannelTokenStream(lexer)
    parser = LDPythonParser(stream)
    parser.removeErrorListeners()
    errorListener = MainErrorListener()
    parser.addErrorListener(errorListener)
    if diagnose:
        diagnosticErrorListener = DiagnosticErrorListener()
        parser.addErrorListener(diagnosticErrorListener)
    tree = parser.file_input()
    if parser.getNumberOfSyntaxErrors() != 0:
        msg = "\n  ".join(errorListener.errors)
        if "extraneous input 'g{'" in msg:
            msg = msg + "\nldpy needs a space after 'g{'"
        exc = SyntaxError(f"ldpy SyntaxError in file {filename}:\n  {msg}")
        exc.filename = filename
        exc.lineno = int(msg[5:msg.index(":")])
        raise exc
    return tree

def printTokens(lexer, tokenTypes):
    i = 0
    while True:
        t:Token = lexer.nextToken()
        print( f"[@{i},{t.start}:{t.stop}='{t.text}',<{t.type}:{tokenTypes[t.type]}>,{t.line}:{t.column} in channel {t.channel}]", file=sys.stderr)
        i += 1
        if t.type == -1:
            break

def debugTokens(input_stream):
    lexer = LDPythonLexer(input_stream)
    import ldpy.grun.lib as lib
    tokenTypes = lib.readTokenTypes("ldpy/rewriter/antlr/LDPython.tokens")
    printTokens(lexer, tokenTypes)

def printTree(tree):
    import ldpy.grun.lib as lib
    tokenTypes = lib.readTokenTypes("ldpy/rewriter/antlr/LDPython.tokens")
    try:
        print(lib.format_tree(tree, True, tokenTypes), file=sys.stderr)
    except Exception as e:
        import traceback
        print(traceback.format_exc(), file=sys.stderr)

def transform_source(source, filename="<none>", namespaces = dict()):
    """Replacement of the .ldpy source to a Python source.
    """
    input_stream = InputStream(source + "\n")
    
    if config.debug_lexer or config.debug_parser or config.debug_ldpy:
        print(f"============== Processing file {filename} ==============", file=sys.stderr)

    if config.debug_lexer:
        print("Tokens are:", file=sys.stderr)
        debugTokens(input_stream)
        input_stream = InputStream(source + "\n")

    tree = parseTree(input_stream, filename, False)
        
    if config.debug_parser:
        print("Parsed tree is:")
        printTree(tree)    

    output = IndentedStringWriter()
    visitor = LDPythonRewriter(output, namespaces)
    try:
        visitor.visit(tree)
    except SyntaxError as exc:
        msg = exc.msg
        exc = SyntaxError(f"ldpy SyntaxError in file {filename}:\n  {msg}")
        exc.filename = filename
        exc.lineno = int(msg[5:msg.index(":")])
        raise exc
    transformed_source = output.getvalue()#.strip("\n")
    
    if config.debug_ldpy:
        pyfilename = filename[len(os.getcwd())+1:-5] + ".py"
        print(f"ldpy>>> =========== Transformed {pyfilename} ============", file=sys.stderr)
        lineno=1
        zfill = 1 if transformed_source.count("\n") == 0 else int(math.log10(transformed_source.count("\n")))+1
        for transformed_line in transformed_source.split("\n"):
            print(f"ldpy>>>{str(lineno).zfill(zfill)}: {transformed_line}", file=sys.stderr)
            lineno+=1
        print("ldpy>>> ------------------------------------", file=sys.stderr)
    
    return transformed_source, visitor.namespaces, visitor.linemap

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

def hook_transform_source(source:str, filename:str, module, callback_params:Config) -> str:
    transformed_source, namespaces, linemap = transform_source(source, filename)
    callback_params.namespaces = namespaces
    callback_params.linemap[filename] = linemap
    return transformed_source

import_hook.create_hook(
    callback_params=config,
    transform_source=hook_transform_source,
    hook_name=__name__,
    extensions=[".ldpy"],
    source_init=lambda:"import rdflib\n__base__ = None\n__namespaces__ = dict()\n"  
)
