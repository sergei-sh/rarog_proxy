""" 
Updated: 2016
Author: Sergei Shliakhtin
Contact: xxx.serj@gmail.com
Notes: Main data flow redirection/request handling happens here
"""

import logging 
import multiprocessing
import os
import queue
import re
import socket
import sys
import time

from proxy.encoding import to_str, to_bytes
from proxy.config import Config
from proxy.const import Const
from proxy.logger import log, log_basic_config, logger, logstate, logrequest 
from proxy.network import NetworkRoutines as net
from proxy.request_reader import RequestReader
from proxy.response_reader import ResponseReader
import proxy.storage

class ProcData:
    """Data related to a single process. Those not process-safe are for parent process
       use only"""
    READY, ACTIVE, DONE_OPEN, DONE_CLOSE = list(range(4))
    def __init__(self):
        self.process_name = None 
        #shared data
        self.status = multiprocessing.Value("i", ProcData.READY)
        self.complete_req = multiprocessing.Value("i",0)
        self.session_req = multiprocessing.Value("i",0)
        self.failed_read_req = multiprocessing.Value("i",0)
        #the parent process use only variables
        self.process = None
        self.process_name = None
        #parent endpoint for sending data to child processes
        self.ipc_socket_parent = None
        self.client_sock = None

class ConnectionWorkerProcess:
    """Handles one process. Get an IPC socket initially which is then used to retrieve 
       a client socket
    """
    #will be called in parent process
    def __init__(self):
        self.is_init = False

    #should be called in child process
    def _init_this_process(self):
        assert not self.is_init
        self.is_init = True
        log_basic_config()
        self._use_cache = ("True" == Config.value(Const.STORAGE_SECTION, "enable_cache"))
        self._storage = None
        self._client_sock = None 
        self._stdout_lock = None
        self._proc_data = None

        if self._use_cache:
            try:
                self._storage = proxy.storage.get_storage()
            except Exception as errv:
                log("Storage creation failed: %s" % str(errv), logging.WARNING)
 
    def __call__(self, process_data, ipc_socket, stdout_lock):
        self._init_this_process()
        self._stdout_lock = stdout_lock
        self._proc_data = process_data
        proxy.logger.init_lock(stdout_lock)

        try:
            self._do_work(ipc_socket)
        except KeyboardInterrupt:
            return

    def _do_work(self, ipc_socket):

        proc_name = multiprocessing.current_process().name

        while 1:
           logstate("wait fd")
           #will block here if no incoming sockets
           self._client_sock = socket.fromfd(net.fd_from_socket(ipc_socket), socket.AF_INET, socket.SOCK_STREAM)
           logstate("got fd")
           self._client_sock.settimeout(0)

           client_ok = self._handle_next_request()
           established = net.is_connected(self._client_sock)
           self._client_sock.close()

           if client_ok and established:
               self._proc_data.status.value = ProcData.DONE_OPEN 
           else:
               self._proc_data.status.value = ProcData.DONE_CLOSE

    def _try_handle_more(self, pipeline_tail, pipeline_depth): 
        """Continue reading pipelined requests if there is pending data being send by client"""
        pipeline_depth += 1
        if pipeline_tail:
            return self._handle_next_request(pipeline_tail, pipeline_depth)
        else:
        #this function is only called for successful control-branches
            return True

    def _handle_next_request(self, pipeline_tail=b"", pipeline_depth=0):
        """Get a request from client, pass to orig server then in case of success
           pass response back to client and cache the response"""

        def _clog(message):
            proc_name = multiprocessing.current_process().name
            if 0 == pipeline_depth:
                message_f = "%s:%s " % (proc_name, message)
            else:
                message_f = "%s:P%i:%s " % (proc_name, pipeline_depth, message)
            log(message_f)


        if not self._client_sock:
            _clog("No client socket")
            return False

        logstate("readclient")
        #get the request from client
        request = RequestReader(self._client_sock, pipeline_tail)                

        if not request.ok(): 
            if request.timeout():
            #timeout is not only a timeout but usually an initial zero-size read on non-blocking socket
            #falls here when getting an expired socket from select
                _clog("X")
            else:
                #failed to read the request completely
                _clog("XX")
                with self._proc_data.failed_read_req.get_lock():
                    self._proc_data.failed_read_req.value += 1
                with self._proc_data.session_req.get_lock():
                    self._proc_data.session_req.value  += 1
            return False
        with self._proc_data.session_req.get_lock():
            self._proc_data.session_req.value  += 1

        if RequestReader.GET != request.method():
                _clog("XXX")
                proc_name = multiprocessing.current_process().name
                with self._proc_data.failed_read_req.get_lock():
                    self._proc_data.failed_read_req.value += 1
                return False
        
        #supporting persistent connection with the client but the server connection is single-use
        #so change keep-alive to close
        # Don't pass client "Connection" to origin server, according to HTTP Spec 14.10 (Header Field Definitions: Connection)

        request_message = RequestReader.set_keep_alive(request.message(), len(request.header()), keep_alive=False)

        fileExists = False
        cache_location = request.cache_location()

        if self._use_cache and self._storage:
            haskey, time_loaded = self._storage.haskey_time(cache_location)
            if haskey:
                loaded_ago = time.time() - time_loaded
                if loaded_ago > float(Config.value(Const.STORAGE_SECTION, "cache_discard_after")):
                    self._storage.erase(cache_location)
                else:
                    outputData = self._storage.fetch(cache_location)
                    if not outputData:
                        #data is being written by another process or read error
                        net.send_all(self._client_sock, Const.RESPONSE_500)
                        return False

                    if net.send_all(self._client_sock, Const.STATUS_LINE_200 + outputData):
                        _clog("C")
                        with self._proc_data.complete_req.get_lock():
                            self._proc_data.complete_req.value += 1
                        #successful reply from cache -> continue with the same socket
                        return self._try_handle_more(request.tail(), pipeline_depth)
                    else:
                        #failed to send cache reply
                        _clog("CX")
                        return False

        #file not found in cache  -sending request to the destination server
        host = request.hostname()
        origin_srv = net.connected_socket(host)
        logstate("recsrv")
        if not net.send_all(origin_srv, request_message):
            origin_srv.close()
            #origin server request sending failed
            _clog("RX")
            return self._try_handle_more(request.tail(), pipeline_depth)
        response = ResponseReader(origin_srv)

        logstate("readsrv")
        #we expect client to keep sending pipelined requests
        response_message = RequestReader.set_keep_alive(response.message(), len(response.header()), keep_alive=True)
        response_message_cache = RequestReader.set_keep_alive(response.response_data(), len(response.header()), keep_alive=True)

        try: origin_srv.shutdown(socket.SHUT_WR) 
        except: pass
        origin_srv.close()

        if not response.ok():
           if response.timeout():
               #empty response connection is shutdown
               _clog("RX")
           else:
               #server stopped transferring in the middle
               _clog("RXX")
           if not net.send_all(self._client_sock, Const.RESPONSE_598):
               #failed to deliver error response to client
               _clog("RRX")
           return False

        logstate("sendclient")                
        if not net.send_all(self._client_sock, response_message):
            #failed sending to client
            _clog("TX")
            return False
        #successful response delivery
        _clog("T")
        with self._proc_data.complete_req.get_lock():
            self._proc_data.complete_req.value  += 1

        if self._use_cache and self._storage:
            if Const.HTTP_OK == response.response_status():
                    haskey, ts = self._storage.haskey_time(cache_location)
                    if not haskey:
                       if not self._storage.save(cache_location, response_message_cache): 
                           #cache write fail                           
                           _clog("CSX")
            else:
                #not saving non-success response                
                _clog("S+" + str(response.response_status()))
        
        #partially read next message -> continue reading this socket
        return self._try_handle_more(request.tail(), pipeline_depth)

               




