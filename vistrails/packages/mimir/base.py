###############################################################################
##
## Copyright (C) 2014-2016, New York University.
## Copyright (C) 2011-2014, NYU-Poly.
## Copyright (C) 2006-2011, University of Utah.
## All rights reserved.
## Contact: contact@vistrails.org
##
## This file is part of VisTrails.
##
## "Redistribution and use in source and binary forms, with or without
## modification, are permitted provided that the following conditions are met:
##
##  - Redistributions of source code must retain the above copyright notice,
##    this list of conditions and the following disclaimer.
##  - Redistributions in binary form must reproduce the above copyright
##    notice, this list of conditions and the following disclaimer in the
##    documentation and/or other materials provided with the distribution.
##  - Neither the name of the New York University nor the names of its
##    contributors may be used to endorse or promote products derived from
##    this software without specific prior written permission.
##
## THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
## AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
## THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
## PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
## CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
## EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
## PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
## OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
## WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
## OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
## ADVISED OF THE POSSIBILITY OF SUCH DAMAGE."
##
###############################################################################

from __future__ import division

import StringIO
import csv
import operator
import os


from vistrails.core.modules.config import ModuleSettings
from vistrails.core.modules.vistrails_module import Module, ModuleError
from ..tabledata.common import get_numpy, TableObject, Table, InternalModuleError

_mimir = None
_jvmhelper = None
_mimirLenses = "[[]]"

class MimirOp(object):
    def __init__(self, op, args):
        """Constructor from a function and its arguments.

        This is the type actually passed on MimirOperation ports. It represents a
        future Mimir operation; the actual operation is only created from
        the QueryMimir module, allowing multiple Ops to be used (and the same
        VisTrails-defined graph to be used from multiple Run modules).

        :type args: dict | collections.Iterable
        """
        self.op = op
        self.args = args

    def build(self, operation_map):
        """Builds the result, by instanciating the operations recursively.
        """
        if self in operation_map:
            return operation_map[self]
        else:
            def build(op):
                if isinstance(op, list):
                    return [build(e) for e in op]
                else:
                    return op.build(operation_map)
            if isinstance(self.args, dict):
                kwargs = dict((k, build(v))
                            for k, v in self.args.iteritems())
                obj = self.op(**kwargs)
            else:
                args = [build(a) for a in self.args]
                obj = self.op(*args)
            operation_map[self] = obj
            return obj


class MimirOperation(Module):
    """A Mimir operation that will be run by Run as part of the graph.
    """
    _settings = ModuleSettings(abstract=True)
    _output_ports = [
        ('output', '(org.vistrails.vistrails.mimir:MimirOperation)')]

        
    def compute(self):
        raise NotImplementedError


class MimirLens(MimirOperation):
    """Creates a Lens in mimir specific type.
    """
    _input_ports = [('input', MimirOperation),
                    ('type', 'basic:String', {'entry_types': "['enum']", 'values': _mimirLenses, 'optional': False, 'defaults': "['TYPE_INFERENCE']"}),
                    ('params', 'basic:String'),
                   ('materialize_input', 'basic:Boolean',
                    {'optional': True, 'defaults': "['False']"})]

    def compute(self):
        input = self.get_input('input')
        type_ = self.get_input('type')
        params = self.get_input_list('params')
        materialize_input = self.get_input('materialize_input')
        self.set_output('output',
                        MimirOp(lambda x: _mimir.createLens(x, _jvmhelper.to_scala_seq(params), type_, materialize_input), [input]))


class MimirView(MimirOperation):
    """Creates a View in mimir with specified query.
    """
    _input_ports = [('input', MimirOperation),
                    ('query', 'basic:String')]

    def compute(self):
        input = self.get_input('input')
        query = self.get_input('query')
        self.set_output('output',
                        MimirOp(lambda x: _mimir.createView(x, query), [input]))



class LoadCSVIntoMimir(MimirOperation):
    """A variable, that update its state between Mimir iterations.
    """
    _input_ports = [('file', '(org.vistrails.vistrails.basic:File)')]
    
    def compute(self):
        file = self.get_input('file').name
        self.set_output('output', MimirOp(lambda: _mimir.loadCSV(file), []))


def count_lines(fp):
    lines = 0
    for line in fp:
        lines += 1
    return lines

def attr(e,n,v): 
    class tmp(type(e)):
        def attr(self,n,v):
            setattr(self,n,v)
            return self
    return tmp(e).attr(n,v)

class MimirCSVTable(TableObject):
    def __init__(self, filename, csv_string, cols_det, rows_det, cell_reasons, header_present, delimiter,
                 skip_lines=0, dialect=None, use_sniffer=True):
        self._rows = None

        self.header_present = header_present
        self.delimiter = delimiter
        self.filename = filename
        self.csv_string = csv_string
        self.cols_det = cols_det
        self.rows_det = rows_det
        self.cell_reasons = cell_reasons
        self.skip_lines = skip_lines
        self.dialect = dialect

        (self.columns, self.names, self.delimiter,
         self.header_present, self.dialect) = \
            self.read_string(csv_string, delimiter, header_present, skip_lines,
                           dialect, use_sniffer)
        if self.header_present:
            self.skip_lines += 1

        self.column_cache = {}

    @staticmethod
    def read_string(csvstring, delimiter=None, header_present=True,
                  skip_lines=0, dialect=None, use_sniffer=True):
        if delimiter is None and use_sniffer is False:
            raise InternalModuleError("Must set delimiter if not using sniffer")

        try:
                fp = StringIO.StringIO()
                fp.write(csvstring)
                fp.seek(0)
                if use_sniffer:
                    first_lines = ""
                    line = fp.readline()
                    for i in xrange(skip_lines):
                        if not line:
                            break
                        line = fp.readline()
                    for i in xrange(5):
                        if not line:
                            break
                        first_lines += line
                        line = fp.readline()
                    sniffer = csv.Sniffer()
                    fp.seek(0)
                    if delimiter is None:
                        dialect = sniffer.sniff(first_lines)
                        delimiter = dialect.delimiter
                        # cannot determine header without sniffing delimiter
                        if header_present is None:
                            header_present = sniffer.has_header(first_lines)

                for i in xrange(skip_lines):
                    line = fp.readline()
                    if not line:
                        raise InternalModuleError("skip_lines greater than "
                                                  "the number of lines in the "
                                                  "file")

                if dialect is not None:
                    reader = csv.reader(fp, dialect=dialect)
                else:
                    reader = csv.reader(fp, delimiter=delimiter)
                result = reader.next()
                column_count = len(result)

                if header_present:
                    column_names = [name.strip() for name in result]
                else:
                    column_names = None
        except IOError:
            raise InternalModuleError("File does not exist")

        return column_count, column_names, delimiter, header_present, dialect
    
    def get_col_det(self, row, col):
        try:
            return self.cols_det[row][col]
        except:
            return True
    
    def get_row_det(self, row):
        try:
            return self.rows_det[row]
        except:
            return True
    
    def get_cell_reason(self, row, col):
        try:
            return self.cell_reasons[row][col]
        except:
            return ""

    def get_column(self, index, numeric=False):
        if (index, numeric) in self.column_cache:
            return self.column_cache[(index, numeric)]

        numpy = get_numpy(False)

        if numeric and numpy is not None:
            result = numpy.loadtxt(
                    self.filename,
                    dtype=numpy.float32,
                    delimiter=self.delimiter,
                    skiprows=self.skip_lines,
                    usecols=[index])
        else:
            fp = StringIO.StringIO()
            fp.write(self.csv_string)
            fp.seek(0)
            for i in xrange(self.skip_lines):
                line = fp.readline()
                if not line:
                    raise ValueError("skip_lines greater than the number "
                                     "of lines in the file")
            if self.dialect is not None:
                reader = csv.reader(fp, dialect=self.dialect)
            else:
                reader = csv.reader(fp, delimiter=self.delimiter)

            getter = operator.itemgetter(index)
            try:
                result = []
                for rownb, row in enumerate(reader, 1):
                    val = getter(row)
                    result.append(val)
            except IndexError:
                raise ValueError("Invalid CSV file: only %d fields on "
                                 "line %d (column %d requested)" % (
                                     len(row), rownb, index))
            if numeric:
                result = [float(e) for e in result]

        self.column_cache[(index, numeric)] = result
        return result

    @property
    def rows(self):
        if self._rows is not None:
            return self._rows
        fp = StringIO.StringIO()
        fp.write(self.csv_string)
        fp.seek(0)
        self._rows = count_lines(fp)
        self._rows -= self.skip_lines
        return self._rows


class QueryMimir(Module):
    """Instanciate and run a Mimir Op to make the results available.
    """
    _input_ports = [('output', MimirOperation, {'depth': 1}),
                    ('include_uncertainty', 'basic:Boolean',
                    {'optional': True, 'defaults': "['True']"}),
                    ('include_reasons', 'basic:Boolean',
                    {'optional': True, 'defaults': "['False']"})]
    
    _output_ports = [('column_count', '(org.vistrails.vistrails.basic:Integer)'),
            ('column_names', '(org.vistrails.vistrails.basic:List)'),
            ('table', Table)]
    
    def compute(self):
        input = self.get_input('output')
        include_uncertainty = self.get_input('include_uncertainty')
        include_reasons = self.get_input('include_reasons')
        
        operation_map = {}
        mimirCallsResults = []
        for op in input:
            mimirCallsResults.append(op.build(operation_map))
        
        for res in mimirCallsResults:
            query = "SELECT * FROM " + res
        
        
        header_present = True
        delimiter = ","
        skip_lines = 0
        dialect = None
        sniff_header = True
        csvStrDet = _mimir.vistrailsQueryMimir(query, include_uncertainty, include_reasons)
        cwd = os.getcwd()
        
        #colDet = csvStrDet.colsDet()
        #print type(colDet)
        
        try:
            table = MimirCSVTable(os.path.join(cwd,res)+".csv", csvStrDet.csvStr(), csvStrDet.colsDet(), csvStrDet.rowsDet(), csvStrDet.celReasons(), header_present, delimiter, skip_lines,
                             dialect, sniff_header)
        except InternalModuleError, e:
            e.raise_module_error(self)

        self.set_output('column_count', table.columns)
        self.set_output('column_names', table.names)
        self.set_output('table', table)
        
        
class RawQuery(Module):
    """Instanciate and run a Mimir Op to make the results available.
    """
    _input_ports = [('raw_query', 'basic:String'),
                    ('include_uncertainty', 'basic:Boolean',
                    {'optional': True, 'defaults': "['True']"}),
                    ('include_reasons', 'basic:Boolean',
                    {'optional': True, 'defaults': "['False']"})]
    
    _output_ports = [('column_count', '(org.vistrails.vistrails.basic:Integer)'),
            ('column_names', '(org.vistrails.vistrails.basic:List)'),
            ('table', Table)]
    
    def compute(self):
        include_uncertainty = self.get_input('include_uncertainty')
        include_reasons = self.get_input('include_reasons')
        raw_query = self.get_input('raw_query')
        
        header_present = True
        delimiter = ","
        skip_lines = 0
        dialect = None
        sniff_header = True
        csvStrDet = _mimir.vistrailsQueryMimir(raw_query, include_uncertainty, include_reasons)
        cwd = os.getcwd()
        
        #colDet = csvStrDet.colsDet()
        #print type(colDet)
        
        try:
            table = MimirCSVTable(os.path.join(cwd,"raw_query")+".csv", csvStrDet.csvStr(), csvStrDet.colsDet(), csvStrDet.rowsDet(), csvStrDet.celReasons(), header_present, delimiter, skip_lines,
                             dialect, sniff_header)
        except InternalModuleError, e:
            e.raise_module_error(self)

        self.set_output('column_count', table.columns)
        self.set_output('column_names', table.names)
        self.set_output('table', table)
        
        



_modules = [MimirOperation, MimirLens, MimirView, LoadCSVIntoMimir, RawQuery, QueryMimir]

wrapped = set(['MimirLens', 'MimirView', 'LoadCSVIntoMimir', 'RawQuery'])
