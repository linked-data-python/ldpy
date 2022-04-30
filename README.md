# Linked-Data Python

The Linked-Data Python package can rewrite a .ldpy file into an equivalent python code.

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

The Linked-Data Python package is a command line application, name `ldpy`. It can also be run as `python -m ldpy`.

```
$ python -m ldpy -h
usage: __main__.py [-h] [-l] [-p] [-d] [-s] [-w] [-x] file

Rewrite a .ldpy file into an equivalent python code.

positional arguments:
  file                  the file to rewrite

optional arguments:
  -h, --help            show this help message and exit
  -l, --debug-lexer     print the lexer output
  -p, --debug-parser    print the parser output
  -d, --diagnose-syntax
                        diagnose the ambiguities in the syntax
  -s, --silent          do not display the output code
  -w, --write-output    write the output python code with the .py extension
  -x, --execute         execute the output cod
```

You can also run a transformation in your own Python code, by importing from the `ldpy` package:

```
from ldpy import *
input_stream = FileStream(file) # or = InputStream(string)
lexer = LDPythonLexer(input_stream)
stream = MultiChannelTokenStream(lexer)
parser = LDPythonParser(stream)
tree = parser.file_input()
if parser.getNumberOfSyntaxErrors() != 0:
    raise Exception("Exception while parsing the input")
output = IndentedStringWriter()
visitor = LDPythonRewriter(output)
visitor.visit(tree)
print("\noutput:\n" + output.getvalue())
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

## Release Notes

### 0.0.1

Initial release of the Linked-Data Python package

