/*
 * The MIT License (MIT)
 *
 * Copyright (c) 2022 by Maxime Lefrançois
 *
 * Permission is hereby granted, free of charge, to any person
 * obtaining a copy of this software and associated documentation
 * files (the "Software"), to deal in the Software without
 * restriction, including without limitation the rights to use,
 * copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the
 * Software is furnished to do so, subject to the following
 * conditions:
 *
 * The above copyright notice and this permission notice shall be
 * included in all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
 * EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
 * OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
 * NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
 * HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
 * WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
 * FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
 * OTHER DEALINGS IN THE SOFTWARE.
 *
 * Project      : ldpython-parser; an ANTLR4 grammar for Linked-Data Python
 *                https://gitlab.com/coswot/linked-data-python/ldpy
 * Developed by : Maxime Lefrançois, maxime.lefrancois@emse.fr
 */
grammar LDPython;

// An ANTLR4 grammar for Linked-Data Python 3, for Python3 target
// All comments that start with "///" are copy-pasted from
// The Python Language Reference: https://docs.python.org/3.3/reference/grammar.html
// This grammar extends the Python 3 grammar from Bart Kiers, bart@big-o.nl available at https://github.com/bkiers/python3-parser
// Changes include: 
// - only use grammar rules supported by MicroPython 1.18
// - add support for Linked Data languages primitives and constructs: 
//     - prefix declaration statements: `@prefix ex: <http://example.org/> .`
//     - base declaration statements: `@base <http://example.org/> .`
//     - IRIs: `<http://example.org/>
//     - Prefixed names: `ex:Person` 
//     - RDF Literals: `"hello"^^xsd:string`, `f"hello {world}"@en`
//     - RDF Graphs: `g{ ex:Person a owl:Class }`
// Furthermore it allows:
// - formatted IRIs: `f<http://example/org/{ id }/>`
// - RDF expression variables in RDF graphs: `g{ ex:Person ex:age ?{ age } }`

tokens { INDENT, DEDENT }

//Note the indentation of code inside

@parser::header{
from ldpy.rewriter import MultiChannelTokenStream
from antlr4.error import Errors
}

@parser::members{
    
def enableWs(self):
    if isinstance(self._input, MultiChannelTokenStream):
        self._input.enable(Token.HIDDEN_CHANNEL)

def disableWs(self):
    if isinstance(self._input, MultiChannelTokenStream):
        self._input.disable(Token.HIDDEN_CHANNEL)

def checkIsA(self):
    if self.getCurrentToken().text != 'a':
        raise Errors.FailedPredicateException(self)

}

@lexer::header{
from antlr4.Token import CommonToken
import re
import importlib

# Allow languages to extend the lexer and parser, by loading the parser dynamically
module_path = __name__[:-5]
language_name = __name__.split('.')[-1]
language_name = language_name[:-5]  # Remove Lexer from name
LanguageParser = getattr(importlib.import_module('{}Parser'.format(module_path)), '{}Parser'.format(language_name))
}

@lexer::members {
is_literal = False
allow_langtag = False

@property
def tokens(self):
    try:
        return self._tokens
    except AttributeError:
        self._tokens = []
        return self._tokens

@property
def indents(self):
    try:
        return self._indents
    except AttributeError:
        self._indents = []
        return self._indents

@property
def opened(self):
    try:
        return self._opened
    except AttributeError:
        self._opened = 0
        return self._opened

@opened.setter
def opened(self, value):
    self._opened = value

@property
def lastToken(self):
    try:
        return self._lastToken
    except AttributeError:
        self._lastToken = None
        return self._lastToken

@lastToken.setter
def lastToken(self, value):
    self._lastToken = value

def reset(self):
    super().reset()
    self.tokens = []
    self.indents = []
    self.opened = 0
    self.lastToken = None

def emitToken(self, t):
    super().emitToken(t)
    self.tokens.append(t)

def nextToken(self):
    if self._input.LA(1) == Token.EOF and self.indents:
        for i in range(len(self.tokens)-1,-1,-1):
            if self.tokens[i].type == Token.EOF:
                self.tokens.pop(i)

        self.emitToken(self.commonToken(LanguageParser.NEWLINE, '\n'))
        while self.indents:
            self.emitToken(self.createDedent())
            self.indents.pop()

        self.emitToken(self.commonToken(LanguageParser.EOF, "<EOF>"))
    next = super().nextToken()
    if next.channel == Token.DEFAULT_CHANNEL:
        self.lastToken = next
    if self.allow_langtag:
        self.is_literal = False
        self.allow_langtag = False
    if self.is_literal:
        self.is_literal = False
        self.allow_langtag = True
    return next if not self.tokens else self.tokens.pop(0)

def createDedent(self):
    dedent = self.commonToken(LanguageParser.DEDENT, "")
    dedent.line = self.lastToken.line
    return dedent

def commonToken(self, type, text, indent=0):
    stop = self.getCharIndex()-1-indent
    start = (stop - len(text) + 1) if text else stop
    return CommonToken(self._tokenFactorySourcePair, type, super().DEFAULT_TOKEN_CHANNEL, start, stop)

@staticmethod
def getIndentationCount(spaces):
    count = 0
    for ch in spaces:
        if ch == '\t':
            count += 8 - (count % 8)
        else:
            count += 1
    return count

def atStartOfInput(self):
    return Lexer.column.fget(self) == 0 and Lexer.line.fget(self) == 1
}

/*
 * parser rules
 */

single_input: NEWLINE | simple_stmt | compound_stmt NEWLINE | base_stmt | prefix_stmt;
file_input: (NEWLINE | stmt)* EOF;
eval_input: testlist NEWLINE* EOF;

decorator: '@' dotted_name ( '(' (arglist)? ')' )? NEWLINE;
decorators: decorator+;
decorated: decorators (classdef | funcdef | async_funcdef);

base_stmt: BASE IRIREF ( SEMI_COLON | DOT )? NEWLINE;
prefix_stmt: PREFIX (NAME? COLON) IRIREF ( SEMI_COLON | DOT )? NEWLINE;

async_funcdef: ASYNC funcdef;
funcdef: 'def' NAME parameters ('->' test)? ':' suite;

parameters: '(' (typedargslist)? ')';
typedargslist: tfpdef ('=' test)? (',' tfpdef ('=' test)?)* (','
       ('*' (tfpdef)? (',' tfpdef ('=' test)?)* (',' '**' tfpdef)? | '**' tfpdef)?)?
     |  '*' (tfpdef)? (',' tfpdef ('=' test)?)* (',' '**' tfpdef)? | '**' tfpdef; // @changed
tfpdef: NAME (':' test)?;
varargslist: vfpdef ('=' test)? (',' vfpdef ('=' test)?)* (','
       ('*' (vfpdef)? (',' vfpdef ('=' test)?)* (',' '**' vfpdef)? | '**' vfpdef)?)?
     |  '*' (vfpdef)? (',' vfpdef ('=' test)?)* (',' '**' vfpdef)? | '**' vfpdef; // micropython

vfpdef: NAME;

//stmt: simple_stmt | compound_stmt; 
//stmt: compound_stmt | simple_stmt; // micropython
stmt: compound_stmt | simple_stmt | base_stmt | prefix_stmt ;
simple_stmt: small_stmt (';' small_stmt)* (';')? NEWLINE;
small_stmt: (expr_stmt | del_stmt | pass_stmt | flow_stmt |
             import_stmt | global_stmt | nonlocal_stmt | assert_stmt);
// expr_stmt: testlist_star_expr (annassign | augassign (yield_expr|testlist) |
//                      ('=' (yield_expr|testlist_star_expr))*);
expr_stmt: testlist_star_expr (augassign (yield_expr|testlist) |
                     ('=' (yield_expr|testlist_star_expr))*);
//annassign: ':' test ('=' test)?;
//annassign: ':' test ('=' (yield_expr|testlist_star_expr))?; // micropython -- conflicts with prefixed names, and micropython ignores types anyways as I can tell. 
testlist_star_expr: (test|star_expr) (',' (test|star_expr))* (',')?;
augassign: ('+=' | '-=' | '*=' | '@=' | '/=' | '%=' | '&=' | '|=' | '^=' |
            '<<=' | '>>=' | '**=' | '//=');
// For normal and annotated assignments, additional restrictions enforced by the interpreter
del_stmt: 'del' exprlist;
pass_stmt: 'pass';
flow_stmt: break_stmt | continue_stmt | return_stmt | raise_stmt | yield_stmt;
break_stmt: 'break';
continue_stmt: 'continue';
return_stmt: 'return' (testlist)?;
yield_stmt: yield_expr;
raise_stmt: 'raise' (test ('from' test)?)?;
import_stmt: import_name | import_from;
import_name: 'import' dotted_as_names;
// note below: the ('.' | '...') is necessary because '...' is tokenized as ELLIPSIS
import_from: ('from' (('.' | '...')* dotted_name | ('.' | '...')+)
              'import' ('*' | '(' import_as_names ')' | import_as_names));
import_as_name: NAME ('as' NAME)?;
dotted_as_name: dotted_name ('as' NAME)?;
import_as_names: import_as_name (',' import_as_name)* (',')?;
dotted_as_names: dotted_as_name (',' dotted_as_name)*;
dotted_name: NAME ('.' NAME)*;
global_stmt: 'global' NAME (',' NAME)*;
nonlocal_stmt: 'nonlocal' NAME (',' NAME)*;
assert_stmt: 'assert' test (',' test)?;

compound_stmt: if_stmt | while_stmt | for_stmt | try_stmt | with_stmt | funcdef | classdef | decorated | async_stmt;
async_stmt: ASYNC (funcdef | with_stmt | for_stmt);
if_stmt: 'if' test ':' suite ('elif' test ':' suite)* ('else' ':' suite)?;
while_stmt: 'while' test ':' suite ('else' ':' suite)?;
for_stmt: 'for' exprlist 'in' testlist ':' suite ('else' ':' suite)?;
try_stmt: ('try' ':' suite
           ((except_clause ':' suite)+
            ('else' ':' suite)?
            ('finally' ':' suite)? |
           'finally' ':' suite));
with_stmt: 'with' with_item (',' with_item)*  ':' suite;
with_item: test ('as' expr)?;
// NB compile.c makes sure that the default except clause is last
except_clause: 'except' (test ('as' NAME)?)?;
suite: simple_stmt | NEWLINE INDENT stmt+ DEDENT;

test: or_test ('if' or_test 'else' test)? | lambdef;
test_nocond: or_test | lambdef_nocond;
lambdef: 'lambda' (varargslist)? ':' test;
lambdef_nocond: 'lambda' (varargslist)? ':' test_nocond;
or_test: and_test ('or' and_test)*;
and_test: not_test ('and' not_test)*;
not_test: 'not' not_test | comparison;
comparison: expr (comp_op expr)*;
// <> isn't actually a valid comparison operator in Python. It's here for the
// sake of a __future__ import described in PEP 401 (which really works :-)
//comp_op: '<'|'>'|'=='|'>='|'<='|'<>'|'!='|'in'|'not' 'in'|'is'|'is' 'not';
comp_op: '<'|'>'|'=='|'>='|'<='|'!='|'in'|'not' 'in'|'is'|'is' 'not';
star_expr: '*' expr;
expr: xor_expr ('|' xor_expr)*;
xor_expr: and_expr ('^' and_expr)*;
and_expr: shift_expr ('&' shift_expr)*;
shift_expr: arith_expr (('<<'|'>>') arith_expr)*;
arith_expr: term (('+'|'-') term)*;
term: factor (('*'|'@'|'/'|'%'|'//') factor)*;
factor: ('+'|'-'|'~') factor | power;
power: atom_expr ('**' factor)?;
atom_expr: (AWAIT)? atom trailer*;
atom: ('(' (yield_expr|testlist_comp)? ')' |
       '[' (testlist_comp)? ']' |
       '{' (dictorsetmaker)? '}' |
       NAME | NUMBER | STRING + | rdf_literal+ | '...' | 'None' | 'True' | 'False' |
       iri | var | xiri | construct_template );
testlist_comp: (test|star_expr) ( comp_for | (',' (test|star_expr))* (',')? );
trailer: '(' (arglist)? ')' | '[' subscriptlist ']' | '.' NAME;
subscriptlist: subscript (',' subscript)* (',')?;
subscript: test | (test)? ':' (test)? (sliceop)?;
sliceop: ':' (test)?;
exprlist: (expr|star_expr) (',' (expr|star_expr))* (',')?;
testlist: test (',' test)* (',')?;
// dictorsetmaker: ( ((test ':' test | '**' expr)
//                    (comp_for | (',' (test ':' test | '**' expr))* (',')?)) |
//                   ((test | star_expr)
//                    (comp_for | (',' (test | star_expr))* (',')?)) );
dictorsetmaker: (test ':' test (comp_for | (',' test ':' test )* (',')?)) |
                (test (comp_for | (',' test)* (',')?)) ;
classdef: 'class' NAME ('(' (arglist)? ')')? ':' suite;

// arglist: argument (',' argument)*  (',')?;
arglist: (argument ',')* (argument (',')?
                         | '*' test (',' argument)* (',' '**' test)?
                         | '**' test); // micropython

// The reason that keywords are test nodes instead of NAME is that using NAME
// results in an ambiguity. ast.c makes sure it's a NAME.
// "test '=' test" is really "keyword '=' test", but we have no such token.
// These need to be in a single rule to avoid grammar that is ambiguous
// to our LL(1) parser. Even though 'test' includes '*expr' in star_expr,
// we explicitly match '*' here, too, to give it proper precedence.
// Illegal combinations and orderings are blocked in ast.c:
// multiple (test comp_for) arguments are blocked; keyword unpackings
// that precede iterable unpackings are blocked; etc.
// argument: ( test (comp_for)? |
//             test '=' test |
//             '**' test |
//             '*' test );
argument: (test (comp_for)? | test '=' test ); // micropython

comp_iter: comp_for | comp_if;
//comp_for: (ASYNC)? 'for' exprlist 'in' or_test (comp_iter)?;
comp_for: 'for' exprlist 'in' or_test (comp_iter)?;
comp_if: 'if' test_nocond (comp_iter)?;

// not used in grammar, but may appear in "node" passed from Parser to Compiler
encoding_decl: NAME;

yield_expr: 'yield' (yield_arg)?;
yield_arg: 'from' test | testlist;

// adapted from SPARQL
construct_template: 'g{' construct_triples? '}';
construct_triples: triples_same_subject ( '.' construct_triples? )?;
triples_same_subject: var_or_term property_list_not_empty | triples_node property_list;
property_list: property_list_not_empty?;
property_list_not_empty: verb object_list ( ';' ( verb object_list )? )*;
verb: {self._input.LT(1).text == 'a'}? NAME  | var_or_iri;
object_list: object_ ( ',' object_ )*;
object_: graph_node;
triples_node: collection | blank_node_property_list;
blank_node_property_list: '[' property_list_not_empty ']';
collection: '(' graph_node+ ')';
graph_node: var_or_term | triples_node;
var_or_term: graph_term | var | xiri | xnode;
var_or_iri: iri | var ;
var: VAR1 | VAR2;
graph_term: iri | rdf_literal | var | NUMBER | 'True' | 'False' | blank_node | nil;
rdf_literal: STRING ( LANGTAG | ( '^^' iri ) )?;
iri: IRIREF | prefixed_name;
prefixed_name: {self.enableWs();} all_names? COLON all_names? {self.disableWs();};
all_names:  DEF | RETURN | RAISE | FROM | IMPORT | AS | GLOBAL | NONLOCAL | ASSERT | IF | ELIF | ELSE | WHILE | FOR | IN | TRY | FINALLY | WITH | EXCEPT | LAMBDA | OR | AND | NOT | IS | NONE | TRUE | FALSE | CLASS | YIELD | DEL | PASS | CONTINUE | BREAK | ASYNC | AWAIT | NAME;
blank_node: BLANK_NODE_LABEL | anon;
nil: OPEN_PAREN CLOSE_PAREN;
anon: OPEN_BRACK CLOSE_BRACK;

xiri: XIRIREF_START test ( XIRIREF_SUB test )* XIRIREF_END;
xnode: 'f{' test '}';

/*
 * lexer rules
 */

IRIREF
    : '<' ( ~('<' | '>' | '"' | '{' | '}' | '|' | '^' | '\\' | '`' | [\u0000-\u0020] ) )* '>'
    ;
XIRIREF_START
    : 'f<' ( ~('<' | '>' | '"' | '{' | '}' | '|' | '^' | '\\' | '`' | [\u0000-\u0020] ) )* '{'
    ;
XIRIREF_SUB
    : '}' ( ~('<' | '>' | '"' | '{' | '}' | '|' | '^' | '\\' | '`' | [\u0000-\u0020] ) )* '{'
    ;
XIRIREF_END
    : '}' ( ~('<' | '>' | '"' | '{' | '}' | '|' | '^' | '\\' | '`' | [\u0000-\u0020] ) )* '>'
    ;

STRING
 : STRING_LITERAL {self.is_literal = True;}
 | BYTES_LITERAL {self.is_literal = True;}
 ;

NUMBER
 : INTEGER
 | FLOAT_NUMBER
 | IMAG_NUMBER
 ;

INTEGER
 : DECIMAL_INTEGER
 | OCT_INTEGER
 | HEX_INTEGER
 | BIN_INTEGER
 ;

DEF : 'def';
RETURN : 'return';
RAISE : 'raise';
FROM : 'from';
IMPORT : 'import';
AS : 'as';
GLOBAL : 'global';
NONLOCAL : 'nonlocal';
ASSERT : 'assert';
IF : 'if';
ELIF : 'elif';
ELSE : 'else';
WHILE : 'while';
FOR : 'for';
IN : 'in';
TRY : 'try';
FINALLY : 'finally';
WITH : 'with';
EXCEPT : 'except';
LAMBDA : 'lambda';
OR : 'or';
AND : 'and';
NOT : 'not';
IS : 'is';
NONE : 'None';
TRUE : 'True';
FALSE : 'False';
CLASS : 'class';
YIELD : 'yield';
DEL : 'del';
PASS : 'pass';
CONTINUE : 'continue';
BREAK : 'break';
ASYNC : 'async';
AWAIT : 'await';

BASE : '@base';
PREFIX : '@prefix';

NEWLINE
 : ( {self.atStartOfInput()}?   SPACES
   | ( '\r'? '\n' | '\r' | '\f' ) SPACES?
   )
   {
tempt = Lexer.text.fget(self)
newLine = re.sub("[^\r\n\f]+", "", tempt)
spaces = re.sub("[\r\n\f]+", "", tempt)
la_char = ""
try:
    la = self._input.LA(1)
    la_char = chr(la)       # Python does not compare char to ints directly
except ValueError:          # End of file
    pass

# Strip newlines inside open clauses except if we are near EOF. We keep NEWLINEs near EOF to
# satisfy the final newline needed by the single_put rule used by the REPL.
try:
    nextnext_la = self._input.LA(2)
    nextnext_la_char = chr(nextnext_la)
except ValueError:
    nextnext_eof = True
else:
    nextnext_eof = False

if self.opened > 0 or nextnext_eof is False and (la_char == '\r' or la_char == '\n' or la_char == '\f' or la_char == '#'):
    self.skip()
else:
    indent = self.getIndentationCount(spaces)
    previous = self.indents[-1] if self.indents else 0
    self.emitToken(self.commonToken(self.NEWLINE, newLine, indent=indent))      # NEWLINE is actually the '\n' char
    if indent == previous:
        self.skip()
    elif indent > previous:
        self.indents.append(indent)
        self.emitToken(self.commonToken(LanguageParser.INDENT, spaces))
    else:
        while self.indents and self.indents[-1] > indent:
            self.emitToken(self.createDedent())
            self.indents.pop()
    }
 ;

NAME
// : ID_START_ASCII ID_CONTINUE_ASCII*
 : PN_CHARS_U PN_CHARS_UN*
 ;

STRING_LITERAL
 : ( [rR] | [uU] | [fF] | ( [fF] [rR] ) | ( [rR] [fF] ) )? ( SHORT_STRING | LONG_STRING )
 ;

BYTES_LITERAL
 : ( [bB] | ( [bB] [rR] ) | ( [rR] [bB] ) ) ( SHORT_BYTES | LONG_BYTES )
 ;

DECIMAL_INTEGER
 : NON_ZERO_DIGIT DIGIT*
 | '0'+
 ;

OCT_INTEGER
 : '0' [oO] OCT_DIGIT+
 ;

HEX_INTEGER
 : '0' [xX] HEX_DIGIT+
 ;

BIN_INTEGER
 : '0' [bB] BIN_DIGIT+
 ;

FLOAT_NUMBER
 : POINT_FLOAT
 | EXPONENT_FLOAT
 ;

IMAG_NUMBER
 : ( FLOAT_NUMBER | INT_PART ) [jJ]
 ;

BLANK_NODE_LABEL
 : '_:' ( PN_CHARS_U | DIGIT ) ((PN_CHARS | DOT)* PN_CHARS)?
 ;

VAR1
 : '?' VARNAME
 ;

VAR2
 : '$' VARNAME
 ;
 
LANGTAG
 : '@' [a-zA-Z]+ ('-' [a-zA-Z0-9]+)* {self.allow_langtag}?
 ;

DOT : '.';
ELLIPSIS : '...';
STAR : '*';
OPEN_PAREN : '(' {self.opened += 1};
CLOSE_PAREN : ')' {self.opened -= 1};
COMMA : ',';
COLON : ':';
SEMI_COLON : ';';
POWER : '**';
ASSIGN : '=';
OPEN_BRACK : '[' {self.opened += 1};
CLOSE_BRACK : ']' {self.opened -= 1};
OR_OP : '|';
XOR : '^';
AND_OP : '&';
LEFT_SHIFT : '<<';
RIGHT_SHIFT : '>>';
ADD : '+';
MINUS : '-';
DIV : '/';
MOD : '%';
IDIV : '//';
NOT_OP : '~';
OPEN_BRACE : '{' {self.opened += 1};
CLOSE_BRACE : '}' {self.opened -= 1};
OPEN_GRAPH : 'g{' {self.opened += 1};
LESS_THAN : '<';
GREATER_THAN : '>';
EQUALS : '==';
GT_EQ : '>=';
LT_EQ : '<=';
NOT_EQ_1 : '<>';
NOT_EQ_2 : '!=';
AT : '@';
ARROW : '->';
ADD_ASSIGN : '+=';
SUB_ASSIGN : '-=';
MULT_ASSIGN : '*=';
AT_ASSIGN : '@=';
DIV_ASSIGN : '/=';
MOD_ASSIGN : '%=';
AND_ASSIGN : '&=';
OR_ASSIGN : '|=';
XOR_ASSIGN : '^=';
LEFT_SHIFT_ASSIGN : '<<=';
RIGHT_SHIFT_ASSIGN : '>>=';
POWER_ASSIGN : '**=';
IDIV_ASSIGN : '//=';

SKIP_
 : ( SPACES | COMMENT | LINE_JOINING ) -> channel(HIDDEN)
 ;

UNKNOWN_CHAR
 : .
 ;

/*
 * fragments
 */

/// shortstring     ::=  "'" shortstringitem* "'" | '"' shortstringitem* '"'
/// shortstringitem ::=  shortstringchar | stringescapeseq
/// shortstringchar ::=  <any source character except "\" or newline or the quote>
fragment SHORT_STRING
 : '\'' ( STRING_ESCAPE_SEQ | ~[\\\r\n\f'] )* '\''
 | '"' ( STRING_ESCAPE_SEQ | ~[\\\r\n\f"] )* '"'
 ;

/// longstring      ::=  "'''" longstringitem* "'''" | '"""' longstringitem* '"""'
fragment LONG_STRING
 : '\'\'\'' LONG_STRING_ITEM*? '\'\'\''
 | '"""' LONG_STRING_ITEM*? '"""'
 ;

/// longstringitem  ::=  longstringchar | stringescapeseq
fragment LONG_STRING_ITEM
 : LONG_STRING_CHAR
 | STRING_ESCAPE_SEQ
 ;

/// longstringchar  ::=  <any source character except "\">
fragment LONG_STRING_CHAR
 : ~'\\'
 ;

/// stringescapeseq ::=  "\" <any source character>
fragment STRING_ESCAPE_SEQ
 : '\\' .
 | '\\' NEWLINE
 ;

/// nonzerodigit   ::=  "1"..."9"
fragment NON_ZERO_DIGIT
 : [1-9]
 ;

/// digit          ::=  "0"..."9"
fragment DIGIT
 : [0-9]
 ;

/// octdigit       ::=  "0"..."7"
fragment OCT_DIGIT
 : [0-7]
 ;

/// hexdigit       ::=  digit | "a"..."f" | "A"..."F"
fragment HEX_DIGIT
 : [0-9a-fA-F]
 ;

/// bindigit       ::=  "0" | "1"
fragment BIN_DIGIT
 : [01]
 ;

/// pointfloat    ::=  [intpart] fraction | intpart "."
fragment POINT_FLOAT
 : INT_PART? FRACTION
 | INT_PART '.'
 ;

/// exponentfloat ::=  (intpart | pointfloat) exponent
fragment EXPONENT_FLOAT
 : ( INT_PART | POINT_FLOAT ) EXPONENT
 ;

/// intpart       ::=  digit+
fragment INT_PART
 : DIGIT+
 ;

/// fraction      ::=  "." digit+
fragment FRACTION
 : '.' DIGIT+
 ;

/// exponent      ::=  ("e" | "E") ["+" | "-"] digit+
fragment EXPONENT
 : [eE] [+-]? DIGIT+
 ;

/// shortbytes     ::=  "'" shortbytesitem* "'" | '"' shortbytesitem* '"'
/// shortbytesitem ::=  shortbyteschar | bytesescapeseq
fragment SHORT_BYTES
 : '\'' ( SHORT_BYTES_CHAR_NO_SINGLE_QUOTE | BYTES_ESCAPE_SEQ )* '\''
 | '"' ( SHORT_BYTES_CHAR_NO_DOUBLE_QUOTE | BYTES_ESCAPE_SEQ )* '"'
 ;

/// longbytes      ::=  "'''" longbytesitem* "'''" | '"""' longbytesitem* '"""'
fragment LONG_BYTES
 : '\'\'\'' LONG_BYTES_ITEM*? '\'\'\''
 | '"""' LONG_BYTES_ITEM*? '"""'
 ;

/// longbytesitem  ::=  longbyteschar | bytesescapeseq
fragment LONG_BYTES_ITEM
 : LONG_BYTES_CHAR
 | BYTES_ESCAPE_SEQ
 ;

/// shortbyteschar ::=  <any ASCII character except "\" or newline or the quote>
fragment SHORT_BYTES_CHAR_NO_SINGLE_QUOTE
 : [\u0000-\u0009]
 | [\u000B-\u000C]
 | [\u000E-\u0026]
 | [\u0028-\u005B]
 | [\u005D-\u007F]
 ;

fragment SHORT_BYTES_CHAR_NO_DOUBLE_QUOTE
 : [\u0000-\u0009]
 | [\u000B-\u000C]
 | [\u000E-\u0021]
 | [\u0023-\u005B]
 | [\u005D-\u007F]
 ;

/// longbyteschar  ::=  <any ASCII character except "\">
fragment LONG_BYTES_CHAR
 : [\u0000-\u005B]
 | [\u005D-\u007F]
 ;

/// bytesescapeseq ::=  "\" <any ASCII character>
fragment BYTES_ESCAPE_SEQ
 : '\\' [\u0000-\u007F]
 ;

fragment SPACES
 : [ \t]+
 ;

fragment COMMENT
 : '#' ~[\r\n\f]*
 ;

fragment LINE_JOINING
 : '\\' SPACES? ( '\r'? '\n' | '\r' | '\f' )
 ;

/// pn_chars_base   ::=  <sparql pn_chars_base AND ascii>
fragment PN_CHARS_BASE
 : [A-Z] 
 | [a-z] 
 ;

/// pn_chars_u   ::=  <sparql pn_chars_u AND ascii>
/// id_start     ::=  <python id_start AND ascii>
fragment PN_CHARS_U // == ID_START
 : PN_CHARS_BASE
 | '_'
 ;

/// pn_chars_un   ::=  <sparql (pn_chars_u OR [0-9]) AND ascii>
fragment PN_CHARS_UN
 : PN_CHARS_U
 | [0-9]
 ;

fragment VARNAME
 : PN_CHARS_U+
 ;

fragment PN_CHARS
 : PN_CHARS_UN
 | '-'
 ;

fragment PN_PREFIX
 : PN_CHARS_BASE ( (PN_CHARS | '.')* PN_CHARS )?
 ;

fragment PN_LOCAL
 : ( PN_CHARS_UN | ':' | PLX ) ( ( PN_CHARS_UN | ':' | PLX | '.')* ( PN_CHARS_UN | ':' | PLX ) )?
 ;

fragment PLX
 : PERCENT | PN_LOCAL_ESC
 ;

fragment PERCENT
 : '%' HEX_DIGIT HEX_DIGIT
 ;

fragment PN_LOCAL_ESC
 : '\\' ( '_' | '~' | '.' | '-' | '!' | '$' | '&' | '\'' | '(' | ')' | '*' | '+' | ',' | ';' | '=' | '/' | '?' | '#' | '@' | '%' )
 ;

/// id_start     ::=  <all characters in general categories Lu, Ll, Lt, Lm, Lo, Nl, the underscore, and characters with the Other_ID_Start property>
// corresponds to PN_CHARS_U
// fragment ID_START_ASCII
//  : '_'
//  | [A-Z]
//  | [a-z]
//  ;

/// id_continue  ::=  <all characters in id_start, plus characters in the categories Mn, Mc, Nd, Pc and others with the Other_ID_Continue property>
// corresponds to PN_CHARS_UN
// fragment ID_CONTINUE_ASCII
//  : ID_START_ASCII
//  | [0-9]
//  ;