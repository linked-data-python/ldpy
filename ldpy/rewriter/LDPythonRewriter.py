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
import secrets
import rdflib
from antlr4 import TerminalNode, Token
from ldpy.rewriter.antlr.LDPythonVisitor import LDPythonVisitor
from ldpy.rewriter.antlr.LDPythonParser import LDPythonParser
from ldpy.rewriter.IndentedStringWriter import IndentedStringWriter
from ldpy.rewriter.Result import Result

SIZE = 3

# This class defines a complete generic visitor for a parse tree produced by LDPythonParser.
class LDPythonRewriter(LDPythonVisitor):
    
    def __init__(self, output:IndentedStringWriter=IndentedStringWriter()):
        self.base:str = None;
        self.namespaces = dict()
        self.output = output

    def visit(self, tree):
        return tree.accept(self)

    def visitChildren(self, node, asarray=False):
        n = node.getChildCount()
        if n==1:
            return node.getChild(0).accept(self)        
        result = Result()
        out = []
        for i in range(n):
            child = node.getChild(i)
            if isinstance(child, LDPythonParser.SuiteContext):
                raise Exception("not to be used when suite!")
            childResult = child.accept(self)
            out.append(childResult.out)
            result.stmts += childResult.stmts
            result.post_stmts += childResult.post_stmts
        if asarray:
            result.out = out
        else:
            result.out = ' '.join(out)
        return result
    
    def visitTerminal(self, node):
        return Result(node.getText())

    # Visit a parse tree produced by LDPythonParser#single_input.
    def visitSingle_input(self, ctx:LDPythonParser.Single_inputContext) -> None:
        if isinstance(ctx.getChild(0), TerminalNode):
            self.output.write("")
            return
        ctx.getChild(0).accept(self)
        if ctx.getChildCount()>1 and isinstance(ctx.getChild(0), TerminalNode):
            self.output.write("")


    # Visit a parse tree produced by LDPythonParser#file_input.
    def visitFile_input(self, ctx:LDPythonParser.File_inputContext) -> None:
        self.output.write("import rdflib")
        n = ctx.getChildCount()
        for i in range(n-1): # ignore the last token which is <EOF>
            child = ctx.getChild(i)
            if isinstance(child, TerminalNode):
                self.output.write("")
            else:
                child.accept(self)
            self.output.write("")


    # Visit a parse tree produced by LDPythonParser#eval_input.
    def visitEval_input(self, ctx:LDPythonParser.Eval_inputContext) -> None:
        raise Exception("not implemented yet")


    # Visit a parse tree produced by LDPythonParser#decorators.
    def visitDecorators(self, ctx:LDPythonParser.DecoratorsContext):
        result = Result()
        result.out = []
        for decorator in ctx.decorator():
            decoratorResult = decorator.accept(self)
            result.out.append(decoratorResult.out)
            result.stmts += decoratorResult.stmts
        return result
        

    # Visit a parse tree produced by LDPythonParser#decorated.
    def visitDecorated(self, ctx:LDPythonParser.DecoratedContext):
        result_decorators = ctx.decorators().accept(self)
        for stmt in result_decorators.stmts:
            self.output.write(stmt)
        ctx.getChild(1).decorators = result_decorators.out
        ctx.getChild(1).accept(self)
        

    # Visit a parse tree produced by LDPythonParser#base_stmt.
    def visitBase_stmt(self, ctx:LDPythonParser.Base_stmtContext) -> None:
        base = ctx.getChild(1).getText()[1:-1]
        self.base = base
        self.output.write(f"# @base <{base}> .")
    

    # Visit a parse tree produced by LDPythonParser#prefix_stmt.
    def visitPrefix_stmt(self, ctx:LDPythonParser.Prefix_stmtContext) -> None:
        prefix = ctx.NAME().getText() if ctx.NAME() else ""
        uri = ctx.IRIREF().getText()[1:-1]
        self.namespaces[prefix] = rdflib.Namespace(uri)
        self.output.write(f"# @prefix {prefix}: <{uri}> .")
    

    # Visit a parse tree produced by LDPythonParser#async_funcdef.
    def visitAsync_funcdef(self, ctx:LDPythonParser.Async_funcdefContext):
        funcdef = ctx.funcdef()
        funcdef.isasync = True
        if hasattr(ctx, "decorators"):
            funcdef.decorators = ctx.decorators
        funcdef.accept(self)


    # Visit a parse tree produced by LDPythonParser#funcdef.
    def visitFuncdef(self, ctx:LDPythonParser.FuncdefContext):
        out = "async " if hasattr(ctx, "isasync") else ""
        result_parameters = ctx.parameters().accept(self)
        out += "def " + ctx.NAME().getText() + result_parameters.out
        if ctx.test():
            result_test = ctx.test().accept(self)
            for stmt in result_test.stmts:
                self.output.write(stmt)
            out += " -> " + result_test.out
        out += ":"
        if hasattr(ctx, "decorators"):
            for decorator in ctx.decorators:
                self.output.write(decorator)
        self.output.write(out)
        # WARNING: les valeurs par défaut des paramètres doivent être à l'intérieur de la fonction, pas à l'exterieur
        # if param = None:
        #     param = param_default
        self.output.indent()
        for stmt in result_parameters.post_stmts:
            self.output.write(stmt)
        self.output.dedent()
        ctx.suite().accept(self)        


    # Visit a parse tree produced by LDPythonParser#typedargslist.
    def visitTypedargslist(self, ctx:LDPythonParser.TypedargslistContext):
        n = ctx.getChildCount()
        result = Result()
        out = []
        i=0
        # check if a test has stmts. make them post_stmts and delete '='
        while i<n:
            child = ctx.getChild(i)
            if isinstance(child, LDPythonParser.TfpdefContext):
                childResult = child.accept(self)
                out.append(childResult.out)
                name = childResult.out.split(":")[0]
                result.stmts += childResult.stmts
            if isinstance(child, TerminalNode) and child.getText() == '=':
                child_testResult = ctx.getChild(i+1).accept(self)
                if child_testResult.stmts:
                    result.post_stmts.append(f"if {name} is None:")
                    for stmt in child_testResult.stmts:
                        result.post_stmts.append(f"    {stmt}")
                    result.post_stmts.append(f"    {name} = {child_testResult.out}")
                    i += 2
                else:
                    out[-1] += '=' + child_testResult.out
            i += 1
        result.out = ', '.join(out)
        return result


    # Visit a parse tree produced by LDPythonParser#simple_stmt.
    def visitSimple_stmt(self, ctx:LDPythonParser.Simple_stmtContext) -> None:
        # transforms small_stmt into simple_stmt
        out = ''
        stmts = 0
        for small_stmt in ctx.small_stmt():
            childResult = small_stmt.accept(self) # type: Result
            if childResult.stmts:
                if stmts !=0:
                    self.output.write(out)
                    out = ''
                    stmts = 0
                for stmt in childResult.stmts:
                    self.output.write(stmt)
                self.output.write(childResult.out)
            else:
                if stmts !=0:
                    out += '; '
                out += childResult.out
                stmts += 1
        if stmts !=0:
            self.output.write(out)
        # self.output.write("") # NEWLINE


    # Visit a parse tree produced by LDPythonParser#del_stmt.
    def visitDel_stmt(self, ctx:LDPythonParser.Del_stmtContext):
        childResult = ctx.exprlist().accept(self)
        result = Result('del ' + childResult.out)
        result.stmts = childResult.stmts 
        return result


    # Visit a parse tree produced by LDPythonParser#return_stmt.
    def visitReturn_stmt(self, ctx:LDPythonParser.Return_stmtContext):
        if not ctx.testlist():
            return Result("return")
        childResult = ctx.testlist().accept(self)
        result = Result('return ' + childResult.out)
        result.stmts = childResult.stmts 
        return result


    # Visit a parse tree produced by LDPythonParser#raise_stmt.
    def visitRaise_stmt(self, ctx:LDPythonParser.Raise_stmtContext):
        result = ctx.test()[0].accept(self)
        result.out = 'raise ' + result.out
        if len(ctx.test()>1):
            result2 = ctx.test()[1].accept(self)
            result.out += ' from ' + result2.out
            result.stmts += result2.stmts
        return result


    # Visit a parse tree produced by LDPythonParser#import_name.
    def visitImport_name(self, ctx:LDPythonParser.Import_nameContext):
        return Result("import " + ctx.dotted_as_names().accept(self).out)


    # Visit a parse tree produced by LDPythonParser#import_from.
    def visitImport_from(self, ctx:LDPythonParser.Import_fromContext):
        return Result(' '.join([ c.accept(self).out for c in ctx.getChildren() ]))


    # Visit a parse tree produced by LDPythonParser#import_as_name.
    def visitImport_as_name(self, ctx:LDPythonParser.Import_as_nameContext) -> Result:
        return Result(' '.join([ c.getText() for c in ctx.getChildren() ]))


    # Visit a parse tree produced by LDPythonParser#dotted_as_name.
    def visitDotted_as_name(self, ctx:LDPythonParser.Dotted_as_nameContext) -> Result:
        result = ctx.dotted_name().accept(self)
        if ctx.AS():
            result.out += ' as ' + ctx.NAME().getText()
        return result

    # Visit a parse tree produced by LDPythonParser#import_as_names.
    def visitImport_as_names(self, ctx:LDPythonParser.Import_as_namesContext) -> Result:
        return Result(', '.join([ c.accept(self).out for c in ctx.import_as_name() ]))


    # Visit a parse tree produced by LDPythonParser#dotted_as_names.
    def visitDotted_as_names(self, ctx:LDPythonParser.Dotted_as_namesContext) -> Result:
        return Result(', '.join([ c.accept(self).out for c in ctx.dotted_as_name() ]))


    # Visit a parse tree produced by LDPythonParser#dotted_name.
    def visitDotted_name(self, ctx:LDPythonParser.Dotted_nameContext) -> Result:
        return Result('.'.join([ c.getText() for c in ctx.NAME() ]))
    

    # Visit a parse tree produced by LDPythonParser#global_stmt.
    def visitGlobal_stmt(self, ctx:LDPythonParser.Global_stmtContext) -> Result:
        return Result('global ' + ', '.join([ c.getText() for c in ctx.NAME() ]))


    # Visit a parse tree produced by LDPythonParser#nonlocal_stmt.
    def visitNonlocal_stmt(self, ctx:LDPythonParser.Nonlocal_stmtContext) -> Result:
        return Result('nonlocal ' + ', '.join([ c.getText() for c in ctx.NAME() ]))


    # Visit a parse tree produced by LDPythonParser#async_stmt.
    def visitAsync_stmt(self, ctx:LDPythonParser.Async_stmtContext):
        child = ctx.getChild(1)
        child.isasync = True
        child.accept(self)


    # Visit a parse tree produced by LDPythonParser#if_stmt.
    def visitIf_stmt(self, ctx:LDPythonParser.If_stmtContext):
        stmts = []
        # the if test
        result_if = ctx.test()[0].accept(self)
        stmts += result_if.stmts
        # the elifs tests
        results_elif = [c.accept(self) for c in ctx.test()[1:]]
        for result_elif in results_elif:
            stmts += result_elif.stmts
        # print the stmts
        for stmt in stmts:
            self.output.write(stmt)
        # the if
        self.output.write("if " + result_if.out + ":")
        ctx.suite()[0].accept(self)
        # the elifs
        for i in range(len(results_elif)):
            self.output.write("elif " + results_elif[i].out + ":")
            ctx.suite()[i+1].accept(self)
        # the else
        self.output.write("else:")
        ctx.suite()[-1].accept(self)


    # Visit a parse tree produced by LDPythonParser#while_stmt.
    def visitWhile_stmt(self, ctx:LDPythonParser.While_stmtContext):
        result_test = ctx.test().accept(self)
        for stmt in result_test.stmts:
            self.output.write(stmt)
        self.output.write("while " + result_test.out + ":")
        ctx.suite()[0].accept(self)        
        if len(ctx.suite())>1:
            self.output.write("else:")
            ctx.suite()[1].accept(self)


    # Visit a parse tree produced by LDPythonParser#for_stmt.
    def visitFor_stmt(self, ctx:LDPythonParser.For_stmtContext):
        out = "async " if hasattr(ctx, "isasync") else ""
        exprlist = ctx.exprlist().accept(self)
        for stmt in exprlist.stmts:
            self.output.write(stmt)
        testlist = ctx.testlist().accept(self)
        for stmt in testlist.stmts:
            self.output.write(stmt)
        out += "while " + exprlist.out + " in " + testlist.out + ":"
        self.output.write(out)
        ctx.suite()[0].accept(self)        
        if len(ctx.suite())>1:
            self.output.write("else:")
            ctx.suite()[1].accept(self)


    # Visit a parse tree produced by LDPythonParser#try_stmt.
    def visitTry_stmt(self, ctx:LDPythonParser.Try_stmtContext):
        results_except_clause = [c.accept(self) for c in ctx.except_clause()]
        for result_except_clause in results_except_clause:
            for stmt in result_except_clause.stmts:
                self.output.write(stmt)
        self.output.write("try:")
        ctx.suite()[0].accept(self)
        n = len(results_except_clause)
        for i in range(n):
            self.output.write(results_except_clause[i].out + ":")
            ctx.suite()[i+1].accept(self)
        for i in range(ctx.getChildCount()-7,ctx.getChildCount()):
            if ctx.getChild(i) == ctx.ELSE():
                self.output.write("else:")
                ctx.getChild(i+2).accept(self)
            elif ctx.getChild(i) == ctx.FINALLY():
                self.output.write("finally:")
                ctx.getChild(i+2).accept(self)
                

    # Visit a parse tree produced by LDPythonParser#with_stmt.
    def visitWith_stmt(self, ctx:LDPythonParser.With_stmtContext):
        out = "async " if hasattr(ctx, "isasync") else ""
        results_with_item = [c.accept(self) for c in ctx.with_item()]
        results_with_item_out = [r.out for r in results_with_item]
        for result_with_item in results_with_item:
            for stmt in result_with_item.stmts:
                self.output.write(stmt)
        out += "with " + ",".join(results_with_item_out)
        self.output.write(out)
        ctx.suite().accept(self)


    # Visit a parse tree produced by LDPythonParser#suite.
    def visitSuite(self, ctx:LDPythonParser.SuiteContext):
        self.output.indent()
        if ctx.simple_stmt():
            ctx.simple_stmt.accept(self)
        for stmt in ctx.stmt():
            stmt.accept(self)
        self.output.dedent()


    # Visit a parse tree produced by LDPythonParser#classdef.
    def visitClassdef(self, ctx:LDPythonParser.ClassdefContext):
        out = []
        n = ctx.getChildCount()
        for i in range(n-1):
            childResult = ctx.getChild(i).accept(self)
            out.append(childResult.out)
            for stmt in childResult.stmts:
                self.output.write(stmt)
        if hasattr(ctx, "decorators"):
            for decorator in ctx.decorators:
                self.output.write(decorator)
        self.output.write(' '.join(out))
        ctx.suite().accept(self)


    # Visit a parse tree produced by LDPythonParser#construct_template.
    def visitConstruct_template(self, ctx:LDPythonParser.Construct_templateContext):
        if not ctx.construct_triples():
            return Result("rdflib.Graph()")
        rdfgraph = "graph_" + secrets.token_hex(SIZE)
        result = Result(rdfgraph)
        result.stmts.append(f"{rdfgraph} = rdflib.Graph()")
        
        childResult = ctx.construct_triples().accept(self)
        for stmt in childResult.stmts:
            if isinstance(stmt, str):
                result.stmts.append(stmt)
            elif isinstance(stmt, tuple):
                result.stmts.append(f"{rdfgraph}.add(({stmt[0]},{stmt[1]},{stmt[2]}))")

        return result

    # Visit a parse tree produced by LDPythonParser#construct_triples.
    def visitConstruct_triples(self, ctx:LDPythonParser.Construct_triplesContext):
        result = Result()
        
        childResult = ctx.triples_same_subject().accept(self)
        result.add_stmts(childResult)
        
        if ctx.construct_triples():
            childResult = ctx.triples_sameconstruct_triples_subject().accept(self)
            result.add_stmts(childResult)

        return result


    # Visit a parse tree produced by LDPythonParser#triples_same_subject.
    def visitTriples_same_subject(self, ctx:LDPythonParser.Triples_same_subjectContext):
        result = Result()
        
        subjectResult = ctx.getChild(0).accept(self)
        subject = subjectResult.out
        result.add_stmts(subjectResult)

        predicateObjectResult = ctx.getChild(1).accept(self)
        result.add_stmts(predicateObjectResult, subject)
        
        return result


    # Visit a parse tree produced by LDPythonParser#property_list.
    def visitProperty_list(self, ctx:LDPythonParser.Property_listContext):
        if ctx.property_list_not_empty():
            return ctx.property_list_not_empty().accept(self)
        else:
            return Result()


    # Visit a parse tree produced by LDPythonParser#property_list_not_empty.
    def visitProperty_list_not_empty(self, ctx:LDPythonParser.Property_list_not_emptyContext):
        result = Result()
        i = 0
        n = ctx.getChildCount()
        while i < n:
            if isinstance(ctx.getChild(i), LDPythonParser.VerbContext):
                verbResult = ctx.getChild(i).accept(self)
                verb = verbResult.out
                result.add_stmts(verbResult)
                i += 1
                object_listResult = ctx.getChild(i).accept(self)
                result.add_stmts(object_listResult, verb)
            i += 1                
        return result


    # Visit a parse tree produced by LDPythonParser#verb.
    def visitVerb(self, ctx:LDPythonParser.VerbContext):
        if isinstance(ctx.getChild(0), TerminalNode):
            return Result("rdflib.RDF.type")
        else:
            return ctx.getChild(0).accept(self)


    # Visit a parse tree produced by LDPythonParser#object_list.
    def visitObject_list(self, ctx:LDPythonParser.Object_listContext):
        result = Result()
        for child in ctx.object_():
            childResult = child.accept(self)
            result.add_stmts(childResult)
            result.stmts.append((childResult.out,))
        return result


    # Visit a parse tree produced by LDPythonParser#blank_node_property_list.
    def visitBlank_node_property_list(self, ctx:LDPythonParser.Blank_node_property_listContext):
        rdfsubject = "bn_" + secrets.token_hex(SIZE)
        result = Result(rdfsubject)
        result.stmts.append(f"{rdfsubject} = rdflib.BNode()")
        childResult = ctx.property_list_not_empty().accept(self)
        for stmt in childResult.stmts:
            if isinstance(stmt, tuple) and len(stmt)<3:
                result.stmts.append((rdfsubject, *stmt))
            else:
                result.stmts.append(stmt)
        return result
    

    # Visit a parse tree produced by LDPythonParser#collection.
    def visitCollection(self, ctx:LDPythonParser.CollectionContext):
        secret = secrets.token_hex(SIZE)
        i = 0
        rdflist = f"list_{secret}_{i}"
        result = Result(rdflist)
        result.stmts.append(f"{rdflist} = rdflib.BNode()")
        n = len(ctx.graph_node())
        while i < n:
            rdflist = f"list_{secret}_{i}"
            childResult = ctx.graph_node()[i].accept(self)
            result.add_stmts(childResult)
            result.stmts.append((rdflist, "rdflib.RDF.first", childResult.out))
            if i < n-1:
                rdfrest = f"list_{secret}_{i+1}"
                result.stmts.append(f"{rdfrest} = rdflib.BNode()")
                result.stmts.append((rdflist, "rdflib.RDF.rest", rdfrest))
            else:
                result.stmts.append((rdflist, "rdflib.RDF.rest", "rdflib.RDF.nil"))
            i += 1
        return result


    # Visit a parse tree produced by LDPythonParser#var.
    def visitVar(self, ctx:LDPythonParser.VarContext):
        if ctx.VAR1() or ctx.VAR2():
            varName = ctx.getText()[1:]
            return Result(f"rdflib.Variable('{varName}')")
        return ctx.getChild(0).accept(self)


    # Visit a parse tree produced by LDPythonParser#graph_term.
    def visitGraph_term(self, ctx:LDPythonParser.Graph_termContext):
        if ctx.NUMBER() or ctx.TRUE() or ctx.FALSE():
            return Result(f"rdflib.Literal({ctx.getChild(0).getText()})")
        return ctx.getChild(0).accept(self)


    # Visit a parse tree produced by LDPythonParser#rdf_literal.
    def visitRdf_literal(self, ctx:LDPythonParser.Rdf_literalContext):
        string = ctx.STRING().getText()
        # if not ctx.iri() and not ctx.LANGTAG():
        #     return Result(string)
        if ctx.iri():
            datatype = ctx.iri().accept(self)
            return Result(f"rdflib.Literal({string},datatype={datatype})")
        elif ctx.LANGTAG():
            lang = ctx.LANGTAG().getText()[1:]
            return Result(f"rdflib.Literal({string},lang='{lang}')")
        else:
            return Result(f"rdflib.Literal({string})")
        

    # Visit a parse tree produced by LDPythonParser#iri.
    def visitIri(self, ctx:LDPythonParser.IriContext):
        if ctx.IRIREF():
            uri = ctx.getText()[1:-1]
            if self.base:
                return Result(f"rdflib.URIRef('{uri}', '{self.base}')")
            else:
                return Result(f"rdflib.URIRef('{uri}')")
        else:
            return ctx.prefixed_name().accept(self)

    # Visit a parse tree produced by LDPythonParser#prefixed_name.
    def visitPrefixed_name(self, ctx:LDPythonParser.Prefixed_nameContext):
        prefix , localName  = ctx.getText().split(":", 1)
        if prefix not in set(self.namespaces):
            offendingToken : Token = ctx.start 
            line = offendingToken.line
            column = offendingToken.column
            raise Exception(f"Error at {line}:{column}: prefix {prefix} is undefined")
        uri = self.namespaces[prefix][localName]
        if self.base:
            return Result(f"rdflib.URIRef('{uri}', '{self.base}')")
        else:
            return Result(f"rdflib.URIRef('{uri}')")


    # Visit a parse tree produced by LDPythonParser#blank_node.
    def visitBlank_node(self, ctx:LDPythonParser.Blank_nodeContext):
        name = "bn_" + secrets.token_hex(SIZE)
        result = Result(name)
        if ctx.BLANK_NODE_LABEL():
            label = ctx.getText()[2:]
            result.stmts.append(f"{name} = rdflib.BNode('{label}')")
        else:
            result.stmts.append(f"{name} = rdflib.BNode()")
        
        return result    


    # Visit a parse tree produced by LDPythonParser#nil.
    def visitNil(self, ctx:LDPythonParser.NilContext):
        return Result("rdflib.RDF.nil")


    # Visit a parse tree produced by LDPythonParser#anon.
    def visitAnon(self, ctx:LDPythonParser.AnonContext):
        name = "bn_" + secrets.token_hex(SIZE)
        result = Result(name)
        result.stmts.append(f"{name} = rdflib.BNode()")
        return result
    
    
    # Visit a parse tree produced by LDPythonParser#xiri.
    def visitXiri(self, ctx:LDPythonParser.XiriContext):
        name = "var_" + secrets.token_hex(SIZE)
        result = Result(name)
        out = []
        string = ctx.XIRIREF_START().getText()[2:-1]
        if len(string)>0:
            out.append(f"'{string}'")
        n = ctx.getChildCount()
        for i in range(1,n,2):
            testResult = ctx.getChild(i).accept(self)
            result.add_stmts(testResult)
            out.append("str(" + testResult.out + ")")
            string = ctx.getChild(i+1).accept(self).out[1:-1]
            if len(string)>0:
                out.append(f"'{string}'")
        iri = ' + '.join(out)
        result.stmts.append(f"{name} = rdflib.URIRef({iri})")
        return result

    # Visit a parse tree produced by LDPythonParser#xiri.
    def visitXnode(self, ctx:LDPythonParser.XnodeContext):
        testResult = ctx.test().accept(self)
        if not testResult.stmts:
            return testResult
        name = "var_" + secrets.token_hex(SIZE)
        result = Result(name)
        result.add_stmts(testResult)
        result.stmts.append(f"{name} = {testResult.out}")
        return result
