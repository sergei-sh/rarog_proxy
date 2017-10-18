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

from proxy import ProxyException
from proxy.const import Const
from proxy.encoding import to_str, to_bytes
import proxy.http_response as Response
from proxy.http_response import add_ok_status
from proxy.config import Config
from proxy.logger import log, log_basic_config, logger, proc_state
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
           proc_state("Wait fd")
           #will block here if no incoming sockets
           self._client_sock = socket.fromfd(net.fd_from_socket(ipc_socket), socket.AF_INET, socket.SOCK_STREAM)
           proc_state("Got fd")
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

    def _tunnel(self, sock_orig, sock_client):            
        import socket
        class TunnelFinish(ProxyException):
            pass
        BUF_SIZE = 4096

        def log_code(code, comment, level=logging.DEBUG):
            proc_name = multiprocessing.current_process().name
            message_f = "%s:%s " % (proc_name, code)
            log(message_f, level)

        def read_all(stream):
            data = b"" 
            while 1:
                try:
                    chunk = stream.recv(BUF_SIZE)
                    data += chunk
                except socket.error as e:
                    if 11 == e.errno:
                        log_code("JN ", "No data")
                        return data, True
                    else:
                        log_code("JErr0 " + str(e), "unknown error")
                        return data, False
                # empty chunk means client shutted down
                if 0 == len(chunk) :
                    log_code("JF", "Tunnel finish")
                    """SEND undelivered"""
                    return data, False

        sock_orig.settimeout(5)                    
        sock_client.settimeout(5)                    

        # log_code("JCl", "")
        log_code("JS", "", level=logging.INFO)
        while 1:
            try:
                cl_data, status = read_all(sock_client)                    
                # log_code("JOr " + str(len(cl_data)), "")
                if cl_data:
                    sock_orig.sendall(cl_data)
                if not status:
                    log_code("JF", "", level=logging.INFO)
                    return

                orig_data, status = read_all(sock_orig)
                # log_code("JCl " + str(len(orig_data)), "")
                if orig_data:
                    sock_client.sendall(orig_data)
                if not status:
                    log_code("JF", "", level=logging.INFO)
                    return

            except OSError as errv:
                log_code("JErr1 " + str(errv.errno) + str(errv), "Socket err")
                return


    def _handle_next_request(self, pipeline_tail=b"", pipeline_depth=0):
        """Get a request from client, pass to orig server then in case of success
           pass response back to client and cache the response
           
           pipeline_tail - next message head chunk; when reading the current message,
                the next message data can be also read partially when pipelining
           pipeline_depth - recursion depth for this pipeline
           
           return - bool, False - done working with this FD, True - wait more data on select"""

        def log_code(code, comment):
            """Log a message code instead of a full message. Usable to fit many messages in one row
            Add process name and reucrsion depth if applicable
            
            code - text to output
            comment - not used
            """
            proc_name = multiprocessing.current_process().name
            if 0 == pipeline_depth:
                message_f = "%s:%s " % (proc_name, code)
            else:
                message_f = "%s:P%i:%s " % (proc_name, pipeline_depth, code)
            log(message_f)


        if not self._client_sock:
            log_code("NCS", "No client socket")
            return False

        proc_state("Readclient")
        #get the request from client
        request = RequestReader(self._client_sock, pipeline_tail)                

        if not request.ok(): 
            if request.timeout():
            #timeout is not only a timeout but usually an initial zero-size read on non-blocking socket
            #falls here when getting an expired socket from select
                log_code("X", "Request time out")
                net.send_all(self._client_sock, Response.RESPONSE_408)
            else:
                #failed to read the request completely
                log_code("XX", "Request parse error")
                with self._proc_data.failed_read_req.get_lock():
                    self._proc_data.failed_read_req.value += 1
                with self._proc_data.session_req.get_lock():
                    self._proc_data.session_req.value  += 1
                net.send_all(self._client_sock, Response.RESPONSE_400)
            return False
        with self._proc_data.session_req.get_lock():
            self._proc_data.session_req.value  += 1

        """REFACTOR BY METHODS"""
        if RequestReader.OTHER == request.method():
            net.send_all(self._client_sock, Response.RESPONSE_501)
            log_code("XXX {}".format(request.method_str), "Unsupported method")
            proc_name = multiprocessing.current_process().name
            with self._proc_data.failed_read_req.get_lock():
                self._proc_data.failed_read_req.value += 1
            return False
        elif RequestReader.CONNECT == request.method():
            host = request.hostname()
            print(host)
            orig_sock = net.connected_socket(host)
            if orig_sock:
                net.send_all(self._client_sock, Response.RESPONSE_200)
                self._tunnel(orig_sock, self._client_sock)                
            else:
                net.send_all(self._client_sock, Response.RESPONSE_502)
            try: origin_sock.shutdown(socket.SHUT_WR) 
            except: pass
            orig_sock.close()
            return False
        else:
            assert RequestReader.GET == request.method()
        
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
                            net.send_all(self._client_sock, Response.RESPONSE_500)
                            return False

                        if net.send_all(self._client_sock, add_ok_status(outputData)):
                            log_code("C", "Sent from cache")
                            with self._proc_data.complete_req.get_lock():
                                self._proc_data.complete_req.value += 1
                            #successful reply from cache -> continue with the same socket
                            return self._try_handle_more(request.tail(), pipeline_depth)
                        else:
                            #failed to send cache reply
                            log_code("CX", "Fail to send from cache")
                            return False

            #file not found in cache  -sending request to the destination server
            host = request.hostname()
            origin_srv = net.connected_socket(host)
            proc_state("Recsrv")
            if not origin_srv or not net.send_all(origin_srv, request_message):
                if origin_srv:
                    origin_srv.close()
                #origin server request sending failed
                log_code("RX", "Origin server communication failed")
                net.send_all(self._client_sock, Response.RESPONSE_502)
                return self._try_handle_more(request.tail(), pipeline_depth)
            response = ResponseReader(origin_srv)

            proc_state("Readsrv")
            #we expect client to keep sending pipelined requests
            response_message = RequestReader.set_keep_alive(response.message(), len(response.header()), keep_alive=True)
            response_message_cache = RequestReader.set_keep_alive(response.response_data(), len(response.header()), keep_alive=True)

            try: origin_srv.shutdown(socket.SHUT_WR) 
            except: pass
            origin_srv.close()

            if not response.ok():
               if response.timeout():
                   #empty response connection is shutdown
                   log_code("RX", "Origin response time out")
               else:
                   #server stopped transferring in the middle
                   log_code("RXX", "Origin truncated response")
               if not net.send_all(self._client_sock, Response.RESPONSE_504):
                   #failed to deliver error response to client
                   log_code("RRX", "Client err response send failed")
               return False

            proc_state("Sendclient")                
            if not net.send_all(self._client_sock, response_message):
                #failed sending to client
                log_code("TX", "Client ok response send failed")
                return False
            #successful response delivery
            # self._client_sock.close()
            log_code("T", "Client response send success")
            with self._proc_data.complete_req.get_lock():
                self._proc_data.complete_req.value  += 1

            if self._use_cache and self._storage:
                if Const.HTTP_OK == response.response_status():
                        haskey, ts = self._storage.haskey_time(cache_location)
                        if not haskey:
                           if not self._storage.save(cache_location, response_message_cache): 
                               #cache write fail                           
                               log_code("CSX", "Cache write fail")
                else:
                    #not saving non-success response                
                    log_code("S+" + str(response.response_status()), "Non-ok from origin")
            
            #partially read next message -> continue reading this socket
            return self._try_handle_more(request.tail(), pipeline_depth)

               




