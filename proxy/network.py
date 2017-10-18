""" 
Updated: 2016
Author: Sergei Shliakhtin
Contact: xxx.serj@gmail.com
Notes: 

All the application network interaction
"""

import array
import multiprocessing
import os
import socket
import struct

from proxy.logger import log
from proxy.logger import proc_error, proc_state
from proxy.encoding import to_str

# Port to connect to if none is given in the URL
DEFAULT_PORT = 80
# Seconds to wait before assuming peer timeout
TIMEOUT = 20 
# To compare "sock_status" output
TCP_ESTABLISHED = 1
# Buffer size of IPC socket
IPC_BUF = 64 

#sends the subject fd through unix ipc_socket
def fd_through_socket(ipc_socket, subject_fd):
    fds = array.array("I", [subject_fd]).tobytes()
    try:
        ancdata=[(socket.SOL_SOCKET, socket.SCM_RIGHTS, fds)]
        assert len(ancdata) <= IPC_BUF
        ipc_socket.sendmsg([b"X"], #just some message to send
            ancdata)
    except OSError as err:
        proc_error("Fd sending failed: %s" % str(err))
        proc_state("Rdsenderror")


#receives an fd through a unix socket
def fd_from_socket(ipc_socket):
    try:
        msg, anc, flags, addr = ipc_socket.recvmsg(IPC_BUF, IPC_BUF)
    except OSError as err:
        proc_error("Fd receiving failed: %s" % str(err))
        proc_state("Fdreqerror")
        return None
    fds = []
    for level, type, data in anc:
        arr = array.array("I")
        arr.frombytes(data)
        fds.extend(arr)
    return fds[0]

def ipc_socket_pair():
    sock0, sock1 = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
    sock0.set_inheritable(1)
    sock0.setblocking(1)
    sock1.set_inheritable(1)
    sock1.setblocking(1)
    return sock0, sock1

def bound_socket(addr, port):
    listener_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        listener_socket.bind((addr, port))
    except OSError:
        proc_error("Failed socket binding to %s:%i" % (addr, port))
        return None
    return listener_socket

def connected_socket(host):
    sender_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sender_socket.settimeout(TIMEOUT)
    host = to_str(host)
    try:
        try:
            host, port = host.split(":")
            port = int(port)
        except ValueError:
            port = DEFAULT_PORT
        sender_socket.connect((host, port))
    except OSError:
        proc_error("Failed to connect socket to %s:%i" % (host, DEFAULT_PORT))
    else:
        return sender_socket

def sock_status(sock):
    format = "B"*7 + "I"*21
    try:
       #socket.fromfd(fd, socket.AF_INET, socket.SOCK_STREAM).
        values = struct.unpack(format, sock.getsockopt(socket.IPPROTO_TCP, socket.TCP_INFO, 92))
        return values[0]
    except OSError as errv:
        proc_error("Failed getting socket status: %s" % str(errv))
        return None

def is_connected(fd):
    return TCP_ESTABLISHED == sock_status(fd)

def send_all(socket, data, debug=False):
    try:
        socket.sendall(data)
        if debug:
            print(data)
        return True
    except OSError as errv:
        proc_error("Sending failed: %s" % str(errv))
        return False

def shutdown(socket_):
    try:
        socket_.shutdown(socket.SHUT_WR)
    except socket.error as e:
        # Already closed - OK
        if get_errno(e) != errno.ENOTCONN:
            raise
    socket_.close()

def tunnel(self, sock_orig, sock_client):            
    """Pipe data between 2 sockets

    This looks awful!
    TODO: Refactor this with SELECT
    
    sock_orig - socket
    sock_client - socket
    """
    BUF_SIZE = 4096
    TIMEOUT = 5 

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

    sock_orig.settimeout(TIMEOUT)                    
    sock_client.settimeout(TIMEOUT)                    

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



