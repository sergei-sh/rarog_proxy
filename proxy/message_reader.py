""" 
Updated: 2016
Author: Sergei Shliakhtin
Contact: xxx.serj@gmail.com
Notes: 

This most probably should have not been implemented by hand, but rather used some 
library call.
"""


import re

from proxy.logger import logger, logerror, logstate

class MessageReader(object):
    """The base class for reading an HTTP message from a socket. Handles both Content-Length and 
       chunked encoding.
    """

    def message(self):
        return self._message
    
    def header(self):
        return self._header

    def ok(self):
        return self._ok

    def timeout(self):
        return self._timeout

    def tail(self):
        return self._tail

    def __init__(self, stream, pipeline_tail=b""):
        self._message = pipeline_tail 
        self._header = b""
        self._ok = False
        self._timeout = False
        self._tail = b""

        BUF_SIZE_SMALL = 50 
        BUF_SIZE = 4096
        first = True
        abort = False
        chunked = False
        while 1:
            logstate("readhdr")
            try:
                chunk = stream.recv(BUF_SIZE_SMALL)
            except OSError as errv:
                self._ok = False
                self._timeout = not self._message
                logerror("Message read failed (1) %s " % str(errv))
                logstate(str(errv))
                return
            except Exception:
                raise
            # empty chunk means client shutted down
            if None == chunk or 0 == len(chunk) :
                abort = True
                break
            # occasional blank lines in the begginning should be ignored
            if (first):
                chunk = chunk.lstrip(b"\r\n")
                chunk = chunk.lstrip(b"\n")
                first = False
            self._message += chunk
            # empty line at the end means end of the _headers section. We only handle GET, without a body, so stop here
            match = re.search(b"(\r\n\r\n|\n\n)", self._message);
            if match:
                logstate("match")
                break
            logstate("notmatch")

        if abort or b"HTTP" not in self._message:
            self._ok = False
            self._timeout = not self._message
            return


        self._header = self._message[:match.start()]
        bodycount = len(self._message[match.end():])
        matchContent = re.search(b"^content-length:\s+(\d+)", self._header, re.IGNORECASE | re.MULTILINE)
        #value is not important: chunked coding should be always included and applied the last
        matchTransfer = re.search(b"^transfer-encoding:\s+", self._header, re.IGNORECASE | re.MULTILINE)
        #if present, content-length is ignored
        if matchTransfer: 
            chunked = True
        elif matchContent:
            chunked = False
            contentLength = int(matchContent.group(1))
        else:
        #_message without body
            self._ok = True
            self._tail = self._message[match.end():]
            return


        chunk = b""           
        try:
            if chunked:
                while 1:                        
                    matchTransferEnd = re.search(b"0\r\n(.*\r\n)?\r\n", self._message[len(self._header):])
                    if matchTransferEnd:
                        self._ok = True
                        break
                    logstate("readbody ch")
                    chunk = stream.recv(BUF_SIZE)
                    if not chunk:
                        self._ok = False
                        break
                    self._message += chunk
            else:

                while 1:
                    bodycount += len(chunk)
                    if bodycount == contentLength:
                        self._ok = True
                        break
                    logstate("readbody cl")
                    if contentLength - bodycount >= BUF_SIZE:
                        chunk = stream.recv(BUF_SIZE)
                    else:
                        chunk = stream.recv(contentLength - bodycount)
                    if not chunk:
                        self._ok = False
                        break
                    self._message += chunk
        except OSError as value:
                logerror("Message read failed (2) ")
                logerror(str(value))
                self._ok = False
                self._timeout = not self._message
                      
    @staticmethod                      
    def set_keep_alive(message, size, keep_alive):
        search_in = message[:size]
        matchConn = re.search(b"^connection:\s+.*$", search_in, re.IGNORECASE | re.MULTILINE)
        if matchConn:
            return message[:matchConn.start()] + b"connection: " + (b"keep-alive" if keep_alive else b"close") + message[matchConn.end():]
        else:
            return message
