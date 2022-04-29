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
from io import TextIOBase, StringIO

class IndentedStringWriter(TextIOBase):
    
    def __init__(self, output:TextIOBase = StringIO()):
        self._indent:int = 0
        self.output = output

    def indent(self):
        self._indent+=1
    
    def dedent(self):
        self._indent-=1
    
    def write(self, s:str="", nl=True):
        if nl==True:
            self.output.write("\n" + " " * 4 * self._indent)
        self.output.write(str(s))
        
    def getvalue(self):
        return self.output.getvalue()

