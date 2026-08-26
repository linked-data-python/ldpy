#!/bin/sh
antlr4 -o ldpy/rewriter/antlr -package ldpy.rewriter.antlr -Xexact-output-dir -Dlanguage=Python3 -visitor -no-listener grammars/LDPython.g4
