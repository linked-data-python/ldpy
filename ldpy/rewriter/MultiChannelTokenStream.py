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
from typing import List
from antlr4.Lexer import Lexer
from antlr4.Token import Token
from antlr4.BufferedTokenStream import BufferedTokenStream

# Fork of CommonTokenStream as explained in https://stackoverflow.com/questions/29060496/allow-whitespace-sections-antlr4/29115489#29115489
class MultiChannelTokenStream(BufferedTokenStream):
    __slots__ = 'channels'
    
    def __init__(self, lexer:Lexer, channels:List[int]=[Token.DEFAULT_CHANNEL]):
        super().__init__(lexer)
        self.channels = channels

    def disable(self, channel:int):
        if channel not in self.channels:
            return
        self.channels.remove(channel)
        self.index = self.nextTokenOnChannel(self.index)

    def enable(self, channel:int):
        if channel in self.channels:
            return
        self.channels += [channel]
        i = self.index
        while i>0 and i == channel:
            i -= 1
        self.index = i

    def adjustSeekIndex(self, i:int):
        return self.nextTokenOnChannel(i)

    def LB(self, k:int):
        if k==0 or (self.index-k)<0:
            return None
        i = self.index
        n = 1
        # find k good tokens looking backwards
        while n <= k:
            # skip off-channel tokens
            i = self.previousTokenOnChannel(i - 1)
            n += 1
        if i < 0:
            return None
        return self.tokens[i]

    def LT(self, k:int):
        self.lazyInit()
        if k == 0:
            return None
        if k < 0:
            return self.LB(-k)
        i = self.index
        n = 1 # we know tokens[pos] is a good one
        # find k good tokens
        while n < k:
            # skip off-channel tokens, but make sure to not look past EOF
            if self.sync(i + 1):
                i = self.nextTokenOnChannel(i + 1)
            n += 1
        return self.tokens[i]

    # Count EOF just once.#/
    def getNumberOfOnChannelTokens(self):
        n = 0
        self.fill()
        for i in range(0, len(self.tokens)):
            t = self.tokens[i]
            if t.channel in self.channels:
                n += 1
            if t.type==Token.EOF:
                break
        return n

    # Given a starting index, return the index of the next token on one of the channels.
    #  Return i if tokens[i] is on one of the channels.  Return the index of the EOF token
    # if there are no tokens on one of the channels between i and EOF.
    #/
    def nextTokenOnChannel(self, i:int):
        self.sync(i)
        if i>=len(self.tokens):
            return len(self.tokens) - 1
        token = self.tokens[i]
        while token.channel not in self.channels:
            if token.type==Token.EOF:
                return i
            i += 1
            self.sync(i)
            token = self.tokens[i]
        return i

    # Given a starting index, return the index of the previous token on channel.
    #  Return i if tokens[i] is on channel. Return -1 if there are no tokens
    #  on channel between i and 0.
    def previousTokenOnChannel(self, i:int):
        while i>=0 and self.tokens[i].channel not in self.channels:
            i -= 1
        return i
