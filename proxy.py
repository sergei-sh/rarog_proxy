""" 
Updated: 2016
Author: Sergei Shliakhtin
Contact: xxx.serj@gmail.com
Parser: Python 3
Notes: 

The main application class and program entry point.

The proxy server can display various HTML pages, rather quick, but the funcionality is very limited.
Tested on Opera, Mozilla.
Testing procedure: set up Proxy in browser's Network Settngs. Open any HTTP website. Monitor active processes
and open sockets in the console.
HTTPS requests should be sent through CONNECT method.
"""

import logging
import multiprocessing
import select
from statistics import mode
import sys
import time

from proxy import storage
from proxy.logger import log, log_basic_config, logger, init_lock
import proxy.network as net
from proxy.connection_worker_process import ConnectionWorkerProcess, ProcData
from proxy.const import Const

def _clog(message):
    """Module-specific logging

    message - str
    """
    log(message, logging.WARNING)
 
class ProxyServer:
    """Accepts incoming connections and passes them to worker processes. The latter
       are created once in a fixed number and then accepted sockets are passed to them
       through UNIX socket"""
    def __init__(self, server_ip, port, max_processes):
        """
        server_ip - str, accept connections on this address
        port - int, accept on this port
        max_processes - number of processes to spawn. Those are spawned once and terminated
            on the application exit
        """ 
        multiprocessing.set_start_method("spawn")
        log_basic_config()
        self._stdout_lock = multiprocessing.Lock()
        init_lock(self._stdout_lock)

        self._server_socket = net.bound_socket(server_ip, port)
        TCP_BACKLOG = 32
        self._server_socket.listen(TCP_BACKLOG)

        #stats-related stuff 
        self._total_req = 1
        self._complete_req = 0
        self._failed_read_req = 0
        self._proc_avg = 0
        self._proc_avg_cnt = 1
        self._proc_vals = []
        self._start_time = None
        self._all_open = []
        #the list of worker processes records
        self._processes = [] 


    def _process_if_done(self, proc_data, input_sockets):
       """After a worker process id done with some FD the latter is either being closed or returned
       back to select() for later read
      
       proc_data - ProcessData
       input_sockets - socket list
       """
       if proc_data.client_sock:
            if ProcData.DONE_OPEN == proc_data.status.value:
                self._count_req(proc_data)
                input_sockets.append(proc_data.client_sock)
                log("B-%i-%s" % (proc_data.client_sock.fileno(), proc_data.process_name))
                proc_data.status.value = ProcData.READY
                proc_data.client_sock = None
            if ProcData.DONE_CLOSE == proc_data.status.value:
                self._count_req(proc_data)
#done with the socket in both parent and child processes
                net.shutdown(proc_data.client_sock)
                self._all_open.remove(proc_data.client_sock)
                log("Cl-%i-%s " % (proc_data.client_sock.fileno(), proc_data.process_name))
                proc_data.client_sock.close()
                proc_data.status.value = ProcData.READY
                proc_data.client_sock = None

    def main_loop(self):
        """Loops infinitely to handle application events until KeyboardInterrupted"""

        input_sockets = [self._server_socket]
        active_proc_num = 0

        # init database, if DB storage is chosen
        storage.get_storage()

        #create child processes
        for _ in range(max_proc):
            ipc_socket_parent, ipc_socket_child = net.ipc_socket_pair()
            #this is used to get statistics and monitor/change state of child process
            new_data = ProcData()
            new_proc = multiprocessing.Process(group=None, target=ConnectionWorkerProcess(), name="p%i" % _, 
                args=(new_data,ipc_socket_child,self._stdout_lock))
            new_data.process_name = new_proc.name
            new_data.ipc_socket_parent = ipc_socket_parent
            new_data.process = new_proc
            self._processes.append(new_data)
            new_proc.start()

        SLEEP_PERIOD = 1

        self._all_open = [self._server_socket,]
        ready = []

        while 1:
            #will block here if no new sockets
            inputs, outputs, failed = select.select(input_sockets, [], input_sockets, SLEEP_PERIOD)
            changes = False

            for sock in inputs:
                if self._server_socket == sock:
                    connection, addr = self._server_socket.accept()
                    #those needed to be passed back to select at the end of the iteration
                    input_sockets.append(connection)
                    #this is just to monitor the list of FDs in charge
                    self._all_open.append(connection)

                else:
                    if None == self._start_time:
                        self._start_time = time.time()
                    #those ready to read go to ready list immediately
                    ready.append(sock)
                    input_sockets.remove(sock)
                    changes = True

            for sock in ready.copy():                
                    assigned = False
                    for proc_data in self._processes:
                        if ProcData.READY == proc_data.status.value:
                            #assign to processes if there are available non-busy ones 
                            ready.remove(sock)
                            proc_data.client_sock = sock
                            log("A-%i-%s " % (sock.fileno(), proc_data.process_name))
                            proc_data.status.value = ProcData.ACTIVE
                            #this is the only way you can pass an open socket to already running process
                            net.fd_through_socket(proc_data.ipc_socket_parent, sock.fileno())
                            assigned = True
                            break
            for sock in input_sockets.copy():
                if not sock == self._server_socket and not net.is_connected(sock):
                #they tend to shut down eventually so cleanup needed
                    input_sockets.remove(sock)
                    sock.close()
                    self._all_open.remove(sock)

            for sock in failed:
                #this surprisingly never happenens, dont know why?
                log("F-%i " % sock.fileno())
                sock.close()
                input_sockets.remove(sock)

            for proc_data in self._processes:
                self._process_if_done(proc_data, input_sockets)
       
            active_proc_num = len([1 for proc_data in self._processes if ProcData.ACTIVE == proc_data.status.value])
            #statistics of active processes, can actually be done at different places
            if changes:
                self._proc_avg += active_proc_num
                self._proc_avg_cnt += 1
                self._proc_vals.append(active_proc_num)

            _clog(".")            
            _clog("\nReqs:%i ActiveProc:%i %i " % (self._complete_req, active_proc_num,  len(self._all_open)) 
                + str([s.fileno() for s in input_sockets])
                + str([s.fileno() for s in ready] ))

    def _count_req(self, proc_data):
        """Pick up the statistics from process going inactive
        
        proc_data - ProcessData
        """
        self._total_req += proc_data.session_req.value
        self._complete_req += proc_data.complete_req.value
        self._failed_read_req += proc_data.failed_read_req.value
        proc_data.session_req.value = 0
        proc_data.complete_req.value = 0
        proc_data.failed_read_req.value = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Print stats and shutdown children
        
        exc_type - exception class 
        exc_value -
        tracebak - 
        """
        if self._start_time is not None:
           elapsed = time.time() - self._start_time 
           _clog("\n\nElapsed: %f Average a.proc count: %f Success: %f Complete: %i Total: %i FailedRead: %i "
               % (elapsed, 
                  self._proc_avg / self._proc_avg_cnt,
                  self._complete_req / self._total_req,
                  self._complete_req,
                  self._total_req,
                  self._failed_read_req))
           _clog("A.proc count mode: %f" % mode(self._proc_vals))

        self._stop_all()

        if exc_type == KeyboardInterrupt:
            _clog("KeyboardInterrupt")
            return True

    def _stop_all(self):            
        """Stop all child processes"""
        pids = [proc_data.process.pid for proc_data in self._processes]
        _clog("Stopping processes {}".format(pids))
        for proc_data in self._processes:
            """They don't have children - OK to terminate"""
            proc_data.process.terminate()



if __name__ == "__main__":
    if len(sys.argv) < 4:
            _clog('Usage : "python ProxyServer.py server_ip server_port max_process_number"\n')
            sys.exit(2)
    
    max_proc = int(sys.argv[3])
    _clog("Max processes: %i" % max_proc)

    with ProxyServer(sys.argv[1], int(sys.argv[2]), max_proc) as proxy:
        proxy.main_loop()

