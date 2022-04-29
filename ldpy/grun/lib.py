# from https://github.com/charmoniumQ/antlr4-python-grun

import enum
import json
import importlib
import subprocess
import shutil
from pathlib import Path
import os
from typing import Tuple, Iterable
import antlr4  # type: ignore
from . import util

def readTokenTypes(path):
    tokenTypes = dict()
    tokenTypes[-1] = "EOF"
    with open(path, 'r') as tokensFile:
        for line in tokensFile:
            i = line.rindex("=")
            tokenTypes[int(line[i+1:])] = line[:i]
    return tokenTypes

def format_tree(
    root: antlr4.ParserRuleContext,
    pretty: bool,
    tokenTypes: dict()
) -> str:
    stack = [(root, True)]
    depth = 0
    buf = []
    while stack:
        node, last = stack.pop()
        if node == "end":
            depth -= 1
            # buf.append(depth * " " if pretty else "")
            # buf.append(")")
            # if not last:
            #     buf.append(" ")
        elif isinstance(node, antlr4.tree.Tree.TerminalNodeImpl):
            buf.append(depth * " " if pretty else "")
            token = node.symbol
            lexer = token.getTokenSource()
            token_type_map = {
                symbolic_id + len(lexer.literalNames) - 1: symbolic_name
                for symbolic_id, symbolic_name in enumerate(lexer.symbolicNames)
            }
            type_ = token_type_map.get(token.type, "literal")
            buf.append(f"({tokenTypes[token.type] if token.type in tokenTypes else token.type} {token.text})")
            if not last:
                buf.append(" ")
            if pretty:
                buf.append("\n")
        else:
            buf.append(depth * " " if pretty else "")
            rule_name = node.parser.ruleNames[node.getRuleIndex()]
            buf.append(f"({rule_name}")
            depth += 1
            children = [] if node.children is None else node.children
            stack.append(("end", last))
            stack.extend(util.first_sentinel(list(children)[::-1]))
            if pretty:
                buf.append("\n")
    return "".join(buf)