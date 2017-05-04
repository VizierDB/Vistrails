###############################################################################
##
## Copyright (C) 2014-2016, New York University.
## Copyright (C) 2013-2014, NYU-Poly.
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

import os
from PyQt4 import QtCore, QtGui

from vistrails.packages.spreadsheet.basic_widgets import SpreadsheetCell, \
    SpreadsheetMode
from vistrails.packages.spreadsheet.spreadsheet_cell import QCellWidget

class TableToSpreadsheetMode(SpreadsheetMode):
    def compute_output(self, output_module, configuration):
        table = output_module.get_input('value')
        self.display_and_wait(output_module, configuration,
                              TableCellWidget, (table,))

class TableCell(SpreadsheetCell):
    """Shows a table in a spreadsheet cell.
    """
    _input_ports = [('table', '(org.vistrails.vistrails.tabledata:Table)')]

    def compute(self):
        table = self.get_input('table')
        self.displayAndWait(TableCellWidget, (table,))


class TableModel(QtCore.QAbstractTableModel): 
    def __init__(self, parent=None, *args): 
        super(TableModel, self).__init__()
        self.datatable = None
        self.detTextColor = QtGui.QColor(255, 96, 96)
        self.rowDetBGColor = QtGui.QColor(200, 200, 200) 
        self.headerNames = None

    def update(self, dataIn):
        self.datatable = dataIn
        if self.datatable.names is not None:
            self.headerNames = self.datatable.names   

    def rowCount(self, parent=QtCore.QModelIndex()):
        return self.datatable.rows 

    def columnCount(self, parent=QtCore.QModelIndex()):
        return self.datatable.columns

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if role == QtCore.Qt.DisplayRole:
            row = index.row()
            col = index.column()
            return self.datatable.get_column(col)[row]
        if role == QtCore.Qt.BackgroundColorRole and hasattr(self.datatable, 'get_col_det'):
            row = index.row()
            col = index.column()
            if not self.datatable.get_row_det(row):
                return self.rowDetBGColor
        if role == QtCore.Qt.ForegroundRole and hasattr(self.datatable, 'get_col_det'):
            row = index.row()
            col = index.column()
            if not self.datatable.get_col_det(row, col):
                return self.detTextColor
        #return QtCore.QAbstractTableModel.data(self,index,role)

    def flags(self, index):
        return QtCore.Qt.ItemIsEnabled
    
    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if role == QtCore.Qt.DisplayRole and orientation == QtCore.Qt.Horizontal:
            return self.headerNames[section]
        return QtCore.QAbstractTableModel.headerData(self, section, orientation, role)
    

class TableCellWidget(QCellWidget):
    save_formats = QCellWidget.save_formats + ["HTML files (*.html)"]

    def __init__(self, parent=None):
        QCellWidget.__init__(self, parent)

        layout = QtGui.QVBoxLayout()
        layout.setContentsMargins(0,0,0,0)

        self.table = QtGui.QTableView()
        
        scrollarea = QtGui.QScrollArea(self)
        scrollarea.setWidgetResizable(True)
        scrollarea.setWidget(self.table)
        layout.addWidget(scrollarea)

        self.setLayout(layout)

    def updateContents(self, inputPorts):
        table, = inputPorts
        self.orig_table = table
        
        self.datamodel = TableModel(self.table)  

        self.table.setSortingEnabled(False)
        
        if hasattr(table, 'get_cell_reason') and not self.table.hasMouseTracking():
            self.table.setMouseTracking(True)
            
        if hasattr(table, 'explain_cell_clicked'):
            self.table.clicked.connect(table.explain_cell_clicked)
            self.table.verticalHeader().sectionClicked.connect(table.explain_row_clicked)
            
        try:
           self.datamodel.update(table)
           self.table.setModel(self.datamodel)
        except:
            raise

        
        #self.table.setSortingEnabled(True)
        #self.table.sortByColumn(0, QtCore.Qt.AscendingOrder)
        self.table.resizeColumnsToContents()
        

    def write_html(self):
        document = ['<!DOCTYPE html>\n'
                    '<html>\n  <head>\n'
                    '    <meta http-equiv="Content-type" content="text/html; '
                            'charset=utf-8" />\n'
                    '    <title>Exported table</title>\n'
                    '    <style type="text/css">\n'
                    'table { border-collapse: collapse; }\n'
                    'td, th { border: 1px solid black; }\n'
                    '    </style>\n'
                    '  </head>\n  <body>\n    <table>\n']
        table = self.orig_table
        if table.names is not None:
            names = table.names
        else:
            names = ['col %d' % n for n in xrange(table.columns)]
        document.append('<tr>\n')
        document.extend('  <th>%s</th>\n' % name for name in names)
        document.append('</tr>\n')
        columns = [table.get_column(col) for col in xrange(table.columns)]
        for row in xrange(table.rows):
            document.append('<tr>\n')
            for col in xrange(table.columns):
                elem = columns[col][row]
                if isinstance(elem, bytes):
                    elem = elem.decode('utf-8', 'replace')
                elif not isinstance(elem, unicode):
                    elem = unicode(elem)
                document.append('  <td>%s</td>\n' % elem)
            document.append('</tr>\n')
        document.append('    </table>\n  </body>\n</html>\n')

        return ''.join(document)

    def dumpToFile(self, filename):
        ext = os.path.splitext(filename)[1].lower()
        if ext in ('.html', '.htm'):
            with open(filename, 'wb') as fp:
                fp.write(self.write_html())
        else:
            super(TableCellWidget, self).dumpToFile(filename)

    def saveToPDF(self, filename):
        document = QtGui.QTextDocument()
        document.setHtml(self.write_html())
        printer = QtGui.QPrinter()
        printer.setOutputFormat(QtGui.QPrinter.PdfFormat)
        printer.setOutputFileName(filename)
        document.print_(printer)


_modules = [TableCell]
