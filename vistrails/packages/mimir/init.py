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


from vistrails.core import debug
from vistrails.core.modules.config import ModuleSettings
from vistrails.core.modules.module_registry import get_module_registry
from vistrails.core.utils import VistrailsInternalError
from py4j.java_gateway import server_connection_started, server_connection_stopped,  server_started, server_stopped, pre_server_shutdown, post_server_shutdown, JavaGateway, GatewayParameters, GatewayClient, CallbackServerParameters
from spylon.simple import SimpleJVMHelpers

import base
import argparse
import os

from .base import MimirOp, MimirOperation, \
    _modules as base_modules, wrapped

_mimirCallInterface = None
_gateway = None
_mimir = None
_jvmhelper = None

class MimirCallInterface(object):

    def __init__(self, gateway):
        self.gateway = gateway

    def callToPython(self, obj):

        print("JVM Who?")
        print(obj)
        self.gateway.jvm.System.out.println("jvm in your python")
        return "spylon"

    class Java:
        implements = ["mimir.PythonMimirCallInterface"]

def jvm_gateway(bindAddr, bindPort):
    gw = JavaGateway(GatewayClient(address=bindAddr,port=bindPort), auto_convert=True, callback_server_parameters=CallbackServerParameters())
    #daemonize_connections=True,daemonize=True
    return gw

def simple_jvm_helper(jvm_gateway):
    j = SimpleJVMHelpers(jvm_gateway)
    return j

def started(sender, **kwargs):
    server = kwargs["server"]
    print("JavaGateway Server started")

def connection_started(sender, **kwargs):
    connection = kwargs["connection"]
    print("JavaGateway Server connection_started")

def connection_stopped(sender, **kwargs):
    connection = kwargs["connection"]
    print("JavaGateway Server ")

def stopped(sender, **kwargs):
    server = kwargs["server"]
    print("JavaGateway Server stopped")

def pre_shutdown(sender, **kwargs):
    server = kwargs["server"]
    print("JavaGateway Server pre_shutdown")

def post_shutdown(sender, **kwargs):
    server = kwargs["server"]
    print("JavaGateway Server post_shutdown")



def initialize():
    #parser = argparse.ArgumentParser(description='Mimir Package Arguments')
    #parser.add_argument('--bindAddr', dest='bindAddr', default='127.0.0.1',
    #                    help='bind address for mimir connection server (default: 127.0.0.1)')
    #parser.add_argument('--bindPort', dest='bindPort', default=33389,
    #                    help='bind port for mimir connection server (default: 33389)')

    #args = parser.parse_args()

    server_started.connect(started)
    global _gateway
    _gateway = jvm_gateway('127.0.0.1', 33388)#args.bindAddr, args.bindPort)
    global _jvmhelper
    _jvmhelper = simple_jvm_helper(_gateway)
    global _mimir
    _mimir = _jvmhelper.gateway.entry_point
    global _mimirCallInterface
    _mimirCallInterface = MimirCallInterface(_gateway)
    _mimir.registerPythonMimirCallListener(_mimirCallInterface)
    global _mimirLenses
    _mimirLenses = []
    _mimirLenses.append( _mimir.getAvailableLenses().split (','))
    base_modules[1]._input_ports[1] = ('type', 'basic:String', {'entry_types': "['enum']", 'values': _mimirLenses, 'optional': False, 'defaults': "['MISSING_VALUE']"})
    global _mimirAdaptiveSchemas
    _mimirAdaptiveSchemas = []
    _mimirAdaptiveSchemas.append( _mimir.getAvailableAdaptiveSchemas().split (','))
    base_modules[8]._input_ports[1] = ('type', 'basic:String', {'entry_types': "['enum']", 'values': _mimirAdaptiveSchemas, 'optional': False, 'defaults': "['TYPE_INFERENCE']"})
    global _viztoolUsers
    _viztoolUsers = []
    _viztoolUsers.append(_mimir.getAvailableViztoolUsers().split(','))
    base_modules[7]._input_ports[2] = ('users', 'basic:String', {'entry_types': "['enum']", 'values': _viztoolUsers, 'optional': False})
    global _viztoolDeployTypes
    _viztoolDeployTypes= []
    _viztoolDeployTypes.append( _mimir.getAvailableViztoolDeployTypes().split (','))
    base_modules[7]._input_ports[3] = ('type', 'basic:String', {'entry_types': "['enum']", 'values': _viztoolDeployTypes, 'optional': False, 'defaults': "['GIS']"})

    server_stopped.connect(
        stopped, sender=_gateway.get_callback_server())
    server_connection_started.connect(
        connection_started,
        sender=_gateway.get_callback_server())
    server_connection_stopped.connect(
        connection_stopped,
        sender=_gateway.get_callback_server())
    pre_server_shutdown.connect(
        pre_shutdown, sender=_gateway.get_callback_server())
    post_server_shutdown.connect(
        post_shutdown, sender=_gateway.get_callback_server())

    base._mimir = _mimir
    base._jvmhelper = _jvmhelper

    # Catch exception if module registry has not been initialized. This is
    # currently necessary when running Mimir modules in Vizier without the
    # Viztrails engine.
    try:
        reg = get_module_registry()
        for module in base_modules:
            reg.add_module(module)
    except VistrailsInternalError as ex:
        pass


def finalize():
    print("Shutting Down Gateway...")
    global _mimir
    _mimir.shutdown()
    global _gateway
    _gateway.shutdown()

###############################################################################
