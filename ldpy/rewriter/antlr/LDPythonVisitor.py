# Generated from grammars/LDPython.g4 by ANTLR 4.12.0
from antlr4 import *
if __name__ is not None and "." in __name__:
    from .LDPythonParser import LDPythonParser
else:
    from LDPythonParser import LDPythonParser

# This class defines a complete generic visitor for a parse tree produced by LDPythonParser.

class LDPythonVisitor(ParseTreeVisitor):

    # Visit a parse tree produced by LDPythonParser#single_input.
    def visitSingle_input(self, ctx:LDPythonParser.Single_inputContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#file_input.
    def visitFile_input(self, ctx:LDPythonParser.File_inputContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#eval_input.
    def visitEval_input(self, ctx:LDPythonParser.Eval_inputContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#decorator.
    def visitDecorator(self, ctx:LDPythonParser.DecoratorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#decorators.
    def visitDecorators(self, ctx:LDPythonParser.DecoratorsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#decorated.
    def visitDecorated(self, ctx:LDPythonParser.DecoratedContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#base_stmt.
    def visitBase_stmt(self, ctx:LDPythonParser.Base_stmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#prefix_stmt.
    def visitPrefix_stmt(self, ctx:LDPythonParser.Prefix_stmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#async_funcdef.
    def visitAsync_funcdef(self, ctx:LDPythonParser.Async_funcdefContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#funcdef.
    def visitFuncdef(self, ctx:LDPythonParser.FuncdefContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#parameters.
    def visitParameters(self, ctx:LDPythonParser.ParametersContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#typedargslist.
    def visitTypedargslist(self, ctx:LDPythonParser.TypedargslistContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#tfpdef.
    def visitTfpdef(self, ctx:LDPythonParser.TfpdefContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#varargslist.
    def visitVarargslist(self, ctx:LDPythonParser.VarargslistContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#vfpdef.
    def visitVfpdef(self, ctx:LDPythonParser.VfpdefContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#stmt.
    def visitStmt(self, ctx:LDPythonParser.StmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#simple_stmt.
    def visitSimple_stmt(self, ctx:LDPythonParser.Simple_stmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#small_stmt.
    def visitSmall_stmt(self, ctx:LDPythonParser.Small_stmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#expr_stmt.
    def visitExpr_stmt(self, ctx:LDPythonParser.Expr_stmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#testlist_star_expr.
    def visitTestlist_star_expr(self, ctx:LDPythonParser.Testlist_star_exprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#augassign.
    def visitAugassign(self, ctx:LDPythonParser.AugassignContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#del_stmt.
    def visitDel_stmt(self, ctx:LDPythonParser.Del_stmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#pass_stmt.
    def visitPass_stmt(self, ctx:LDPythonParser.Pass_stmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#flow_stmt.
    def visitFlow_stmt(self, ctx:LDPythonParser.Flow_stmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#break_stmt.
    def visitBreak_stmt(self, ctx:LDPythonParser.Break_stmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#continue_stmt.
    def visitContinue_stmt(self, ctx:LDPythonParser.Continue_stmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#return_stmt.
    def visitReturn_stmt(self, ctx:LDPythonParser.Return_stmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#yield_stmt.
    def visitYield_stmt(self, ctx:LDPythonParser.Yield_stmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#raise_stmt.
    def visitRaise_stmt(self, ctx:LDPythonParser.Raise_stmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#import_stmt.
    def visitImport_stmt(self, ctx:LDPythonParser.Import_stmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#import_name.
    def visitImport_name(self, ctx:LDPythonParser.Import_nameContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#import_from.
    def visitImport_from(self, ctx:LDPythonParser.Import_fromContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#import_as_name.
    def visitImport_as_name(self, ctx:LDPythonParser.Import_as_nameContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#dotted_as_name.
    def visitDotted_as_name(self, ctx:LDPythonParser.Dotted_as_nameContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#import_as_names.
    def visitImport_as_names(self, ctx:LDPythonParser.Import_as_namesContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#dotted_as_names.
    def visitDotted_as_names(self, ctx:LDPythonParser.Dotted_as_namesContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#dotted_name.
    def visitDotted_name(self, ctx:LDPythonParser.Dotted_nameContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#global_stmt.
    def visitGlobal_stmt(self, ctx:LDPythonParser.Global_stmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#nonlocal_stmt.
    def visitNonlocal_stmt(self, ctx:LDPythonParser.Nonlocal_stmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#assert_stmt.
    def visitAssert_stmt(self, ctx:LDPythonParser.Assert_stmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#compound_stmt.
    def visitCompound_stmt(self, ctx:LDPythonParser.Compound_stmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#async_stmt.
    def visitAsync_stmt(self, ctx:LDPythonParser.Async_stmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#if_stmt.
    def visitIf_stmt(self, ctx:LDPythonParser.If_stmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#while_stmt.
    def visitWhile_stmt(self, ctx:LDPythonParser.While_stmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#for_stmt.
    def visitFor_stmt(self, ctx:LDPythonParser.For_stmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#try_stmt.
    def visitTry_stmt(self, ctx:LDPythonParser.Try_stmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#with_stmt.
    def visitWith_stmt(self, ctx:LDPythonParser.With_stmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#with_item.
    def visitWith_item(self, ctx:LDPythonParser.With_itemContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#except_clause.
    def visitExcept_clause(self, ctx:LDPythonParser.Except_clauseContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#suite.
    def visitSuite(self, ctx:LDPythonParser.SuiteContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#test.
    def visitTest(self, ctx:LDPythonParser.TestContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#test_nocond.
    def visitTest_nocond(self, ctx:LDPythonParser.Test_nocondContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#lambdef.
    def visitLambdef(self, ctx:LDPythonParser.LambdefContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#lambdef_nocond.
    def visitLambdef_nocond(self, ctx:LDPythonParser.Lambdef_nocondContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#or_test.
    def visitOr_test(self, ctx:LDPythonParser.Or_testContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#and_test.
    def visitAnd_test(self, ctx:LDPythonParser.And_testContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#not_test.
    def visitNot_test(self, ctx:LDPythonParser.Not_testContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#comparison.
    def visitComparison(self, ctx:LDPythonParser.ComparisonContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#comp_op.
    def visitComp_op(self, ctx:LDPythonParser.Comp_opContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#star_expr.
    def visitStar_expr(self, ctx:LDPythonParser.Star_exprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#expr.
    def visitExpr(self, ctx:LDPythonParser.ExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#xor_expr.
    def visitXor_expr(self, ctx:LDPythonParser.Xor_exprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#and_expr.
    def visitAnd_expr(self, ctx:LDPythonParser.And_exprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#shift_expr.
    def visitShift_expr(self, ctx:LDPythonParser.Shift_exprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#arith_expr.
    def visitArith_expr(self, ctx:LDPythonParser.Arith_exprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#term.
    def visitTerm(self, ctx:LDPythonParser.TermContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#factor.
    def visitFactor(self, ctx:LDPythonParser.FactorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#power.
    def visitPower(self, ctx:LDPythonParser.PowerContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#atom_expr.
    def visitAtom_expr(self, ctx:LDPythonParser.Atom_exprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#atom.
    def visitAtom(self, ctx:LDPythonParser.AtomContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#testlist_comp.
    def visitTestlist_comp(self, ctx:LDPythonParser.Testlist_compContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#trailer.
    def visitTrailer(self, ctx:LDPythonParser.TrailerContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#subscriptlist.
    def visitSubscriptlist(self, ctx:LDPythonParser.SubscriptlistContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#subscript.
    def visitSubscript(self, ctx:LDPythonParser.SubscriptContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#sliceop.
    def visitSliceop(self, ctx:LDPythonParser.SliceopContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#exprlist.
    def visitExprlist(self, ctx:LDPythonParser.ExprlistContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#testlist.
    def visitTestlist(self, ctx:LDPythonParser.TestlistContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#dictorsetmaker.
    def visitDictorsetmaker(self, ctx:LDPythonParser.DictorsetmakerContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#classdef.
    def visitClassdef(self, ctx:LDPythonParser.ClassdefContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#arglist.
    def visitArglist(self, ctx:LDPythonParser.ArglistContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#argument.
    def visitArgument(self, ctx:LDPythonParser.ArgumentContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#comp_iter.
    def visitComp_iter(self, ctx:LDPythonParser.Comp_iterContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#comp_for.
    def visitComp_for(self, ctx:LDPythonParser.Comp_forContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#comp_if.
    def visitComp_if(self, ctx:LDPythonParser.Comp_ifContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#encoding_decl.
    def visitEncoding_decl(self, ctx:LDPythonParser.Encoding_declContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#yield_expr.
    def visitYield_expr(self, ctx:LDPythonParser.Yield_exprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#yield_arg.
    def visitYield_arg(self, ctx:LDPythonParser.Yield_argContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#construct_template.
    def visitConstruct_template(self, ctx:LDPythonParser.Construct_templateContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#construct_triples.
    def visitConstruct_triples(self, ctx:LDPythonParser.Construct_triplesContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#triples_same_subject.
    def visitTriples_same_subject(self, ctx:LDPythonParser.Triples_same_subjectContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#property_list.
    def visitProperty_list(self, ctx:LDPythonParser.Property_listContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#property_list_not_empty.
    def visitProperty_list_not_empty(self, ctx:LDPythonParser.Property_list_not_emptyContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#verb.
    def visitVerb(self, ctx:LDPythonParser.VerbContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#object_list.
    def visitObject_list(self, ctx:LDPythonParser.Object_listContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#object_.
    def visitObject_(self, ctx:LDPythonParser.Object_Context):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#triples_node.
    def visitTriples_node(self, ctx:LDPythonParser.Triples_nodeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#blank_node_property_list.
    def visitBlank_node_property_list(self, ctx:LDPythonParser.Blank_node_property_listContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#collection.
    def visitCollection(self, ctx:LDPythonParser.CollectionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#graph_node.
    def visitGraph_node(self, ctx:LDPythonParser.Graph_nodeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#var_or_term.
    def visitVar_or_term(self, ctx:LDPythonParser.Var_or_termContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#var_or_iri.
    def visitVar_or_iri(self, ctx:LDPythonParser.Var_or_iriContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#var.
    def visitVar(self, ctx:LDPythonParser.VarContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#graph_term.
    def visitGraph_term(self, ctx:LDPythonParser.Graph_termContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#rdf_literal.
    def visitRdf_literal(self, ctx:LDPythonParser.Rdf_literalContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#iri.
    def visitIri(self, ctx:LDPythonParser.IriContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#prefixed_name.
    def visitPrefixed_name(self, ctx:LDPythonParser.Prefixed_nameContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#all_names.
    def visitAll_names(self, ctx:LDPythonParser.All_namesContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#blank_node.
    def visitBlank_node(self, ctx:LDPythonParser.Blank_nodeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#nil.
    def visitNil(self, ctx:LDPythonParser.NilContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#anon.
    def visitAnon(self, ctx:LDPythonParser.AnonContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#firi.
    def visitFiri(self, ctx:LDPythonParser.FiriContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by LDPythonParser#fnode.
    def visitFnode(self, ctx:LDPythonParser.FnodeContext):
        return self.visitChildren(ctx)



del LDPythonParser