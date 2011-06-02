###########################################################################
##
## Copyright (C) 2006-2010 University of Utah. All rights reserved.
##
## This file is part of VisTrails.
##
## This file may be used under the terms of the GNU General Public
## License version 2.0 as published by the Free Software Foundation
## and appearing in the file LICENSE.GPL included in the packaging of
## this file.  Please review the following to ensure GNU General Public
## Licensing requirements will be met:
## http://www.opensource.org/licenses/gpl-license.php
##
## If you are unsure which license is appropriate for your use (for
## instance, you are interested in developing a commercial derivative
## of VisTrails), please contact us at vistrails@sci.utah.edu.
##
## This file is provided AS IS with NO WARRANTY OF ANY KIND, INCLUDING THE
## WARRANTY OF DESIGN, MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE.
##
############################################################################

from PyQt4 import QtCore, QtGui

class BaseView(object):
    """ BaseView is the base class for the views in VisTrails.


    """

    def __init__(self):
        self.controller = None
        self.title = None
        self.index = -1
        self.tab_idx = -1

        self.layout = {}
        self.set_default_layout()
        self.action_links = {}
        self.action_defaults = {}
        self.set_action_defaults()
        self.set_action_links()

    def set_default_layout(self):
        raise Exception("Class must define the layout")

    def set_action_links(self):
        raise Exception("Class must define the action links")

    def set_action_defaults(self):
        raise Exception("Class must define the action defaults")
    
    def set_title(self, title):
        self.title = title

    def get_title(self):
        return self.title

    def get_index(self):
        return self.index

    def set_index(self, index):
        self.index = index

    def get_tab_idx(self):
        return self.tab_idx

    def set_tab_idx(self, tab_idx):
        self.tab_idx = tab_idx

    def set_controller(self, controller):
        pass

    def changeEvent(self, event):
        if event.type() == QtCore.QEvent.WindowTitleChange:
            self.emit(QtCore.SIGNAL("windowTitleChanged"), self)
        QtGui.QWidget.changeEvent(self, event)