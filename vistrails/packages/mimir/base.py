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
import json



from PyQt4.QtGui import QDesktopWidget, QListWidget, QListWidgetItem, QPixmap, QVBoxLayout, QHBoxLayout, QApplication, QLabel, QMessageBox, QPushButton, QWidget, QFormLayout, QLineEdit, QDialog, QInputDialog
from PyQt4 import QtCore

import vistrails.core.interpreter.cached 

from vistrails.core.modules.config import ModuleSettings
from vistrails.core.modules.vistrails_module import Module, ModuleError
from ..tabledata.common import get_numpy, TableObject, Table, InternalModuleError
from vistrails.core.modules.basic_modules import Null

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
                   ('make_input_certain', 'basic:Boolean',
                    {'optional': True, 'defaults': "['False']"}),
                    ('materialize', 'basic:Boolean',
                    {'optional': True, 'defaults': "['False']"})]

    def compute(self):
        input = self.get_input('input')
        type_ = self.get_input('type')
        params = self.get_input_list('params')
        make_input_certain = self.get_input('make_input_certain')
        materialize = self.get_input('materialize')
        self.set_output('output',
                        MimirOp(lambda x: _mimir.createLens(x, _jvmhelper.to_scala_seq(params), type_, make_input_certain, materialize), [input]))
                        
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


class ReasonRepairDialog(QDialog):
    def __init__(self, reasons, reason, parent = None):
        super(ReasonRepairDialog, self).__init__(parent)
        
        self.reason = reason
        self.reasons = reasons
        self.items = self.reasons.mkString("-*-*-").split("-*-*-")   
        self.reasonChoices = None
        self.reasonIdx = self.items.index(self.reason)
        
        self.layout = QFormLayout(self)
        
        self.btn1 = QPushButton("Repair Choice")
        self.btn1.clicked.connect(self.getRepair)
        self.le1 = QLineEdit()
        self.layout.addRow(self.btn1,self.le1)
        
        self.repairButton = QPushButton('Repair')
        self.repairButton.clicked.connect(self.doRepair)
        self.cancelButton = QPushButton('Cancel')
        self.cancelButton.clicked.connect(self.doCancel)
        self.layout.addRow(self.cancelButton,self.repairButton)
        
            
    def getRepair(self):
        repair = _mimir.repairReason(self.reasons, self.reasonIdx)
        repairJson = json.loads(repair.toJSON())
        if repairJson['values']:
            self.reasonChoices = repairJson['values']
            items = map(lambda x: x['choice'], self.reasonChoices)
            item, ok = QInputDialog.getItem(self, "Select A Repair", 
                                            "List of Repairs", items, 0, False)        
        if ok and item:
            self.le1.setText(item)
     
    def doRepair(self):
        _mimir.feedback(self.reasons, self.reasonIdx, False, self.le1.text())
        self.done(QDialog.Accepted)
        
    def doCancel(self):
        self.done(QDialog.Rejected)
  
  
class ExplanationListItem (QWidget):
    def __init__ (self, parent = None):
        super(ExplanationListItem, self).__init__(parent)
        self.textQVBoxLayout = QVBoxLayout()
        self.textUpQLabel    = QLabel()
        self.textDownQLabel  = QLabel()
        self.textDownQLabel.setWordWrap(True);
        self.textQVBoxLayout.addWidget(self.textUpQLabel)
        self.textQVBoxLayout.addWidget(self.textDownQLabel)
        self.allQHBoxLayout  = QHBoxLayout()
        self.iconQLabel      = QLabel()
        self.allQHBoxLayout.addWidget(self.iconQLabel, 0)
        self.allQHBoxLayout.addLayout(self.textQVBoxLayout, 1)
        self.setLayout(self.allQHBoxLayout)
        # setStyleSheet
        self.textUpQLabel.setStyleSheet('''
            color: rgb(0, 0, 0); font-weight:bold;
        ''')
        self.textDownQLabel.setStyleSheet('''
            color: rgb(86, 32, 32); font-weight:bold;
        ''')
        self.iconQLabel.setStyleSheet("margin-left:10px; margin-right: 15px;")

    def setTextUp (self, text):
        self.textUpQLabel.setText(text)

    def setTextDown (self, text):
        self.textDownQLabel.setText(text)

    def getTextDown (self):
        return self.textDownQLabel.text()
    
    def setIcon (self, imagePath):
        self.iconQLabel.setPixmap(QPixmap(imagePath))
      
    
class ExplanationDialog(QWidget):
    def __init__(self, reasons, query, rowProv, col, source_module_id, parent = None):
        super(ExplanationDialog, self).__init__(parent)
        
        self.query = query
        self.rowProv = rowProv
        self.col = col
        self.source_module_id = source_module_id
        self.loadReasons(reasons)
        screenCenter = QDesktopWidget().availableGeometry().center()
        self.setGeometry(screenCenter.x()-350, screenCenter.y()-300, 700, 600)
        
    def loadReasons(self, reasons):
        self.removeChildren()
        self.repairDialog = None
        self.selectedReasonIndex = None 
        self.reasons = reasons
        self.items = self.reasons.mkString("-*-*-").split("-*-*-")   
        
        self.explanationList = QListWidget()
        for text in self.items:
            # Create QCustomQWidget
            myQCustomQWidget = ExplanationListItem()
            myQCustomQWidget.setTextUp("Reason:")
            myQCustomQWidget.setTextDown(text)
            myQCustomQWidget.setIcon("uncertainty.png")
            # Create QListWidgetItem
            myQListWidgetItem = QListWidgetItem(self.explanationList)
            # Set size hint
            myQListWidgetItem.setSizeHint(myQCustomQWidget.sizeHint())
            # Add QListWidgetItem into QListWidget
            self.explanationList.addItem(myQListWidgetItem)
            self.explanationList.setItemWidget(myQListWidgetItem, myQCustomQWidget)
        
        self.explanationList.itemClicked.connect(self.listClicked)
        self.explanationList.setStyleSheet( "QListView{show-decoration-selected:1}QListWidget::item { border-bottom: 1px solid black; border-radius: 5px; font-size:12px; font-weight:bold; }QListView::item:alternate{background:#EEE}QListView::item:selected{border:1px solid #6a6ea9}QListView::item:selected:!active{background:qlineargradient(x1: 0,y1: 0,x2: 0,y2: 1,stop: 0 #d1e1fc,stop: 1 #b8d1fc)}QListView::item:selected:active{background:qlineargradient(x1: 0,y1: 0,x2: 0,y2: 1,stop: 0 #a5deff,stop: 1 #5bc3ff)}QListView::item:hover{background:qlineargradient(x1: 0,y1: 0,x2: 0,y2: 1,stop: 0 #f9fbff,stop: 1 #e2ecff)}" )
        
        self.vbox = QVBoxLayout()
        self.vbox.addWidget(self.explanationList)
        self.hbox = QHBoxLayout()
        
        self.acknowledgeButton = QPushButton('Acknowledge', self)
        self.acknowledgeButton.clicked.connect(self.doAcknowledge)
        self.repairButton = QPushButton('Repair')
        self.repairButton.clicked.connect(self.doRepair)
        self.cancelButton = QPushButton('Done')
        self.cancelButton.clicked.connect(self.doCancel)
        
        self.hbox.addWidget(self.cancelButton)
        self.hbox.addStretch()
        self.hbox.addWidget(self.repairButton)
        self.hbox.addWidget(self.acknowledgeButton)
        
        #self.vbox.addStretch()
        self.vbox.addLayout(self.hbox)
        self.setLayout(self.vbox)
        
    def removeChildren(self):
        if self.layout() != None:
            QWidget().setLayout(self.layout())
    
    def listClicked(self,item):
        self.selectedReasonIndex = self.explanationList.indexFromItem(item).row()
        
    def doRepair(self):
        if self.selectedReasonIndex == None:
            QMessageBox.information(self, "Repair Reason", "Can not repair reason. No Item Selected. Please select a reason and try again.")
        else:
            self.repairDialog = ReasonRepairDialog(self.reasons, self.items[self.selectedReasonIndex], self) 
            if self.repairDialog.exec_() == QDialog.Accepted:
                QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
                if self.col == None:
                    explainReasons = _mimir.explainRow(self.query, self.rowProv) 
                else:
                    explainReasons = _mimir.explainCell(self.query, self.col, self.rowProv)
                QApplication.restoreOverrideCursor()
                self.loadReasons(explainReasons)
                vistrails.core.interpreter.cached.CachedInterpreter.clean_modules_id([self.source_module_id])
        
    def doAcknowledge(self):
        if self.selectedReasonIndex == None:
            QMessageBox.information(self, "Acknowledge Reason", "Can not acknowledge reason. No Item Selected. Please select a reason and try again.")
        else:
            _mimir.feedback(self.reasons, self.selectedReasonIndex, True, "")
            QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            if self.col == None:
                explainReasons = _mimir.explainRow(self.query, self.rowProv) 
            else:
                explainReasons = _mimir.explainCell(self.query, self.col, self.rowProv)
            QApplication.restoreOverrideCursor()
            self.loadReasons(explainReasons)
            vistrails.core.interpreter.cached.CachedInterpreter.clean_modules_id([self.source_module_id])
            
        
    def doCancel(self):
        self.close()
   

class MimirCSVTable(TableObject):
    def __init__(self, filename, query, csv_string, cols_det, rows_det, cell_reasons, prov, source_module_id, header_present, delimiter,
                 skip_lines=0, dialect=None, use_sniffer=True):
        self._rows = None

        self.header_present = header_present
        self.delimiter = delimiter
        self.filename = filename
        self.query = query
        self.csv_string = csv_string
        self.cols_det = cols_det
        self.rows_det = rows_det
        self.cell_reasons = cell_reasons
        self.rows_prov = prov
        self.source_module_id = source_module_id
        self.skip_lines = skip_lines
        self.dialect = dialect
        self.msgBox = None
        self.repairDialog = None
        self.explainDialog = None
        
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
        
    def get_row_prov(self, row):
        try:
            return self.rows_prov[row]
        except:
            return ""
    
    def get_cell_reason(self, index):
        try:
            row = index.row()
            col = index.column()
            return self.cell_reasons[row][col]
        except:
            return ""

    def explain_row_clicked(self, row):
        print("explain_cell_clicked %d" % (row))
        if not self.get_row_det(row):
            #QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            #explainStr = _mimir.explainRow(self.query, self.get_row_prov(row))
            #QApplication.restoreOverrideCursor()
            #QMessageBox.about(None, "Explanation of Row", "Explanation of Row Uncertainty:\n%s" % (explainStr) )
            QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            try:
                explainReasons = _mimir.explainRow(self.query, self.get_row_prov(row))
                self.explainDialog = ExplanationDialog(explainReasons, self.query, self.get_row_prov(row), None, self.source_module_id)
                QApplication.restoreOverrideCursor()
                self.explainDialog.show()
            except:
                QApplication.restoreOverrideCursor()
            
    def explain_cell_clicked(self, index):
        #print("explain_cell_clicked %d, %d" % (tableItem.row()+1, tableItem.column()-1))
        row = index.row()
        col = index.column()
        if not self.get_col_det(row, col):
            QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            
            explainReasons = _mimir.explainCell(self.query, col, self.get_row_prov(row))
            self.explainDialog = ExplanationDialog(explainReasons, self.query, self.get_row_prov(row), col, self.source_module_id)
            QApplication.restoreOverrideCursor()
            self.explainDialog.show()
            #self.msgBox = QMessageBox()
            #self.msgBox.setIcon(QMessageBox.Information)
            #self.msgBox.setText("Explanation of Cell Uncertainty:\n\n%s" % (explainReasons.mkString(",\n\n")))
            #self.msgBox.setWindowTitle("Explanation of Cell")
            #ackButton = QPushButton('Repair...')
            #ackButton.setProperty("row", row)
            #ackButton.setProperty("col", col)
            #ackButton.setProperty("reasons", explainReasons)
            #self.msgBox.addButton(ackButton, QMessageBox.YesRole)
            #self.msgBox.addButton(QPushButton('Close'), QMessageBox.NoRole)
            #self.msgBox.buttonClicked.connect(self.feedbackCell)
            #QApplication.restoreOverrideCursor()
            #retval = self.msgBox.exec_()
        
            QApplication.restoreOverrideCursor()
            
    def feedbackCell(self, button):
        if self.msgBox.buttonRole(button) == QMessageBox.YesRole:
            #_mimir.feedbackCell(self.query, button.property("col"), button.property("row")+1, "ack")
            #print(_mimir.repairReason(button.property("reasons"), 0).exampleString)
            self.repairDialog = ReasonRepairDialog(button.property("reasons"))
            self.repairDialog.show()

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
            table = MimirCSVTable(os.path.join(cwd,res)+".csv", query, csvStrDet.csvStr(), csvStrDet.colsDet(), csvStrDet.rowsDet(), csvStrDet.celReasons(), csvStrDet.prov(), self.moduleInfo['moduleId'], header_present, delimiter, skip_lines,
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
            table = MimirCSVTable(os.path.join(cwd,"raw_query")+".csv", raw_query, csvStrDet.csvStr(), csvStrDet.colsDet(), csvStrDet.rowsDet(), csvStrDet.celReasons(), csvStrDet.prov(), header_present, delimiter, skip_lines,
                             dialect, sniff_header)
        except InternalModuleError, e:
            e.raise_module_error(self)

        self.set_output('column_count', table.columns)
        self.set_output('column_names', table.names)
        self.set_output('table', table)
        
        
class TableToPlot(Module):
    """Convert Mimir CSV table to plotable x and y.
    """
    _input_ports = [('name', 'basic:String'),
                    ('x_column', '(org.vistrails.vistrails.basic:Integer)'),
                    ('y_column', '(org.vistrails.vistrails.basic:Integer)'),
                    ('null_replacement', 'basic:String',
                    {'optional': True, 'defaults': "['nan']"}),
                    ('table', Table)]
    
    _output_ports = [('x', '(org.vistrails.vistrails.basic:List)'),
            ('y', '(org.vistrails.vistrails.basic:List)')
            ]
    
    def compute(self):
        name = self.get_input('name')
        #x_cols = self.get_input_list('x_column')
        #y_cols = self.get_input_list('y_column')
        x_col = self.get_input('x_column')
        y_col = self.get_input('y_column')
        null_replacement = self.get_input('null_replacement')
        #tables = self.get_input_list('table')
        table = self.get_input('table')
        
        #x_list = []
        #y_list = []
        
        #for index, table in enumerate(tables):
        #    x_list = x_list + [i.replace('NULL', null_replacement) for i in map(str.strip, tables[index].get_column(x_cols[index]))]
        #    y_list = y_list + [i.replace('NULL', null_replacement) for i in map(str.strip, tables[index].get_column(y_cols[index]))]

        #x_list, y_list = zip(*sorted(zip(x_list, y_list)))
        
        x_list = [i.replace('NULL', null_replacement) for i in map(str.strip, table.get_column(x_col))]
        y_list = [i.replace('NULL', null_replacement) for i in map(str.strip, table.get_column(y_col))]
 
        self.set_output('x', x_list)
        self.set_output('y', y_list)
    

_modules = [MimirOperation, MimirLens, MimirView, LoadCSVIntoMimir, RawQuery, QueryMimir, TableToPlot]

wrapped = set(['MimirLens', 'MimirView', 'LoadCSVIntoMimir', 'RawQuery', 'TableToPlot'])
