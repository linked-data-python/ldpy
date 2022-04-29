#
# The MIT License (MIT)
#
# Copyright (c) 2022 by Maxime Lefrançois
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
# Project      : ldpython-parser; Linked-Data Python to Python/Micropython Rewriter
#                https://gitlab.com/coswot/linked-data-python/ldpy
# Developed by : Maxime Lefrançois, maxime.lefrancois@emse.fr
#
import sys
from antlr4 import FileStream, Token
from ldpy.rewriter import *
import argparse

def debugTokens(input_stream):
    lexer = LDPythonLexer(input_stream)
    import ldpy.grun.lib as lib
    tokenTypes = lib.readTokenTypes("ldpy/rewriter/antlr/LDPython.tokens")
    printTokens(lexer, tokenTypes)

def parseTree(input_stream): 
    lexer = LDPythonLexer(input_stream)
    stream = MultiChannelTokenStream(lexer)
    parser = LDPythonParser(stream)
    tree = parser.file_input()
    if parser.getNumberOfSyntaxErrors() != 0:
        raise Exception("Exception while parsing the input")
    return tree

def printTree(tree):
    import ldpy.grun.lib as lib
    tokenTypes = lib.readTokenTypes("ldpy/rewriter/antlr/LDPython.tokens")
    try:
        print(lib.format_tree(tree, True, tokenTypes))
    except Exception as e:
        import traceback
        print(traceback.format_exc())
    
def execResult(code): # from https://stackoverflow.com/a/47337130
    from io import StringIO
    old_stdout = sys.stdout
    redirected_output = sys.stdout = StringIO()
    try:
        exec(code)
    except:
        raise 
    finally: # !
        sys.stdout = old_stdout # !

    print(redirected_output.getvalue())
    
    
def printTokens(lexer, tokenTypes):
    i = 0
    while True:
        t:Token = lexer.nextToken()
        print( f"[@{i},{t.start}:{t.stop}='{t.text}',<{t.type}:{tokenTypes[t.type]}>,{t.line}:{t.column} in channel {t.channel}]")
        i += 1
        if t.type == -1:
            break

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Rewrite a .ldpy file into an equivalent python code.')
    parser.add_argument('-l', '--debug-lexer', dest='lexer', action='store_true', default=False,
                        help='print the lexer output')
    parser.add_argument('-p', '--debug-parser', dest='parser', action='store_true', default=False,
                        help='print the parser output')
    parser.add_argument('-s', '--silent', dest='silent', action='store_true', default=False,
                        help='do not display the output code')
    parser.add_argument('-x', '--execute', dest='exec', action='store_true', default=False,
                        help='execute the output code')
    parser.add_argument('file', metavar='file', type=str,
                        help='the file to rewrite')
    args = parser.parse_args(sys.argv[1:])
    
    input_stream = FileStream(args.file)
    
    if args.lexer:
        print("Tokens are:")
        debugTokens(input_stream)
        input_stream = FileStream(args.file)
    
    tree = parseTree(input_stream)
    
    if args.parser:
        print("Parsed tree is:")
        printTree(tree)

    output = IndentedStringWriter()
    visitor = LDPythonRewriter(output)
    visitor.visit(tree)

    if not args.silent:
        print("\noutput:\n" + output.getvalue())

    if args.exec:
        execResult(output.getvalue())
    
    