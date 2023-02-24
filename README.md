# Linked-Data Python

The Linked-Data Python package allow to run .ldpy scripts, run a ldpy interactive console, and import .ldpy library modules.

![](https://gitlab.com/coswot/ldpy/-/raw/master/ldpyIcon.png)

## Installation

You can install the Linked-Data Python 
```
pip install linked-data-python
```

## The Linked-Data Python syntax

The extension ["linked-data-python" for Visual Studio Code](https://marketplace.visualstudio.com/items?itemName=MaximeLefrancois.linked-data-python) enables the syntax highlighting for Linked-Data Python source files (extensions .ldpy).

The Linked-Data Python grammar only uses grammar rules supported by MicroPython 1.18, and adds support for Linked Data languages primitives and constructs: 

- prefix declaration statements: `@prefix ex: <http://example.org/> .`
- base declaration statements: `@base <http://example.org/> .`
- IRIs: `<http://example.org/>
- Prefixed names: `ex:Person` 
- RDF literals: `"hello"^^xsd:string`, `f"hello {world}"@en`
- RDF graphs: `g{ ex:Person a owl:Class ; rdfs:label "Person"@en }`

Furthermore, it allows:

- formatted IRIs: `f<http://example/org/{ id }/>`
- formatted nodes in RDF graphs: `f{ ex:Person ex:age ?{ age } }`

Example programs are available in the `examples` folder of the source code repository.


# How to use

## In the command line

The Linked-Data Python package is a command line application, name `ldpy`. It can also be run as `python -m ldpy`.

```
$ python -m ldpy -h
usage: __main__.py [-h] [-v] [-l] [-p] [-s] [-i] [-m MODULE | source]

ldpy extends the Python syntax with primitives from the Semantic Web such as namespaces, RDF terms, and RDF graphs.

If no source is given, ldpy will start an interactive console.

positional arguments:
  source                Program read from script file. The file extension may be .ldpy or .py.

optional arguments:
  -h, --help            show this help message and exit
  -v, --version         only displays the current version.
  -l, --debug-lexer     print the lexer output
  -p, --debug-parser    print the parser output
  -s, --show_changes    shows the transformed code before it is executed.
  -i                    starts the interactive console after executing a source
  -m MODULE, --module MODULE
                        Run library module as a script. The module may be a .ldpy or a .py file.
```

## As a module

```
import ldpy

ldpy.config.debug_ldpy = True # print transformed source  
ldpy.config.debug_lexer = False # print tokens
ldpy.config.debug_parser = False # print syntax tree

ldpy.transform_source(source) # transform a Linked-Data Python source into a Python source
```

## Run from the source code

### 1. Dependencies

```
# cd ldpy
pip install -r requirements.txt
```

### 2. Generate the parser

Generate the `SWPythonLexer`, `SWPythonParser`, and `SWPythonVisitor` using ANTLR4:

```
# cd ldpy
antlr4 -o ldpy/rewriter/antlr -package ldpy.rewriter.antlr -Xexact-output-dir -Dlanguage=Python3 -visitor -no-listener grammars/LDPython.g4
```

