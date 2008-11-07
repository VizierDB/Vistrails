############################################################################
##
## Copyright (C) 2006-2007 University of Utah. All rights reserved.
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
"""Main file for running VisTrails in server mode"""

if __name__ == '__main__':
    import core.requirements
    core.requirements.check_pyqt4()

    from PyQt4 import QtGui
    import gui.application_server
    import sys
    import os
    try:
        v = gui.application_server.start_server()
        app = gui.application_server.VistrailsServer()
    except SystemExit, e:
        sys.exit(e)
    except Exception, e:
        print "Uncaught exception on initialization: %s" % e
        import traceback
        traceback.print_exc()
        sys.exit(255)
     
    v = app.run_server()
    gui.application_server.stop_server()
    sys.exit(v)