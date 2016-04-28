
import array
import os
import socket
import struct

from proxy.logger import logerror, logstate

class NetworkRoutines:
    DEFAULT_PORT = 80
    TIMEOUT = 10 
    TCP_ESTABLISHED = 1
    IPC_BUF = 64 

    @staticmethod
#sends the subject fd through unix ipc_socket
    def fd_through_socket(ipc_socket, subject_fd):
        fds = array.array("I", [subject_fd]).tobytes()
        try:
            ancdata=[(socket.SOL_SOCKET, socket.SCM_RIGHTS, fds)]
            assert len(ancdata) <= NetworkRoutines.IPC_BUF
            ipc_socket.sendmsg([b"X"], #just some message to send
                ancdata)
        except OSError as err:
            logerror("fd sending failed: %s" % str(err))
            logstate("fdsenderror")


    @staticmethod
#receives an fd through a unix socket
    def fd_from_socket(ipc_socket):
        try:
            msg, anc, flags, addr = ipc_socket.recvmsg(NetworkRoutines.IPC_BUF, NetworkRoutines.IPC_BUF)
        except OSError as err:
            logerror("fd receiving failed: %s" % str(err))
            logstate("fdreqerror")
            return None
        fds = []
        for level, type, data in anc:
            arr = array.array("I")
            arr.frombytes(data)
            fds.extend(arr)
        return fds[0]

    @staticmethod
    def ipc_socket_pair():
        sock0, sock1 = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
        sock0.set_inheritable(1)
        sock0.setblocking(1)
        sock1.set_inheritable(1)
        sock1.setblocking(1)
        return sock0, sock1

    @staticmethod
    def bound_socket(addr, port):
        listener_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            listener_socket.bind((addr, port))
        except OSError:
            logerror("Failed socket binding to %s:%i" % (addr, port))
            return None
        return listener_socket

    @staticmethod
    def connected_socket(host):
        sender_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sender_socket.settimeout(NetworkRoutines.TIMEOUT)
        try:
            sender_socket.connect((host, NetworkRoutines.DEFAULT_PORT))
        except OSError:
            logerror("Failed to connect socket to %s:%i" % (host, NetworkRoutines.DEFAULT_PORT))
        return sender_socket

    @staticmethod
    def sock_status(sock):
        format = "B"*7 + "I"*21
        try:
           #socket.fromfd(fd, socket.AF_INET, socket.SOCK_STREAM).
            values = struct.unpack(format, sock.getsockopt(socket.IPPROTO_TCP, socket.TCP_INFO, 92))
            return values[0]
        except OSError as errv:
            logerror("Failed getting socket status: %s" % str(errv))
            return None

    @staticmethod
    def is_connected(fd):
        return NetworkRoutines.TCP_ESTABLISHED == NetworkRoutines.sock_status(fd)

    @staticmethod
    def send_all(socket, data):
        try:
            socket.sendall(data)
            return True
        except OSError as errv:
            logerror("Sending failed: %s" % str(errv))
            return False
    
