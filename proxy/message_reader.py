""" 
Updated: 2016
Author: Sergei Shliakhtin
Contact: xxx.serj@gmail.com
Notes: 

This most probably should have not been implemented by hand, but rather used some 
library call.
"""

import re

from proxy.logger import logger, proc_error, proc_debug

class MessageReader(object):
    """The base class for reading an HTTP message from a socket. Handles both Content-Length and 
       chunked encoding.
    """

    def __init__(self, stream, pipeline_tail=b""):
        """Read message from stream finding its ending according to its Content-Length or chunked encoding, or peer
        shutdown

        stream - socket to read from
        pipeline_tail - bytes from this request, already read as the tail of 
            previous message
        """
        self.message = pipeline_tail 
        self.header = b""
        self.ok = False
        self.timeout = False
        self.tail = b""

        BUF_SIZE_SMALL = 50 
        BUF_SIZE = 4096
        first = True
        abort = False
        chunked = False

        """Read request/response line and headers"""
        while 1:
            proc_debug("Readhdr")
            try:
                chunk = stream.recv(BUF_SIZE_SMALL)
            except OSError as errv:
                if 11 == errv.errno and self.message:
                    self.ok = True
                    proc_error("Timeout while reading - OK (0) %s " % str(errv))
                    self.message += b"\r\n\r\n"
                    return
                self.timeout = not self.message
                proc_error("Message read failed (1) %s " % str(errv))
                proc_debug(str(errv))
                return
            # empty chunk means client shutted down
            if None == chunk or 0 == len(chunk) :
                abort = True
                break
            # occasional blank lines in the begginning should be ignored
            if (first):
                chunk = chunk.lstrip(b"\r\n")
                chunk = chunk.lstrip(b"\n")
                first = False
            self.message += chunk
            # empty line at the end means end of the _headers section. We only handle GET, without a body, so stop here
            match = re.search(b"(\r\n\r\n|\n\n)", self.message);
            if match:
                proc_debug("Match")
                break
            proc_debug("Notmatch")

        if abort or b"HTTP" not in self.message:
            self.ok = False
            self.timeout = not self.message
            return


        self.header = self.message[:match.start()]
        bodycount = len(self.message[match.end():])
        matchContent = re.search(b"^content-length:\s+(\d+)", self.header, re.IGNORECASE | re.MULTILINE)
        #When using Transfer-Encoding, chunked coding is
        # and applied the last according to 3.6 Protocol Paramters: Transfer Codings
        # otherwise, message end is by closing the connection
        matchTransfer = re.search(b"^transfer-encoding:\s+", self.header, re.IGNORECASE | re.MULTILINE)
        #if present, content-length is ignored
        if matchTransfer: 
            chunked = True
        elif matchContent:
            chunked = False
            contentLength = int(matchContent.group(1))
        else:
        #_message without body
            self.ok = True
            self.tail = self.message[match.end():]
            return


        """Read body"""
        chunk = b""           
        try:
            if chunked:
                while 1:                        
                    # Search for 0-chunk and possibly a trailer following a newline
                    matchTransferEnd = re.search(b"0\r\n(.*\r\n)?\r\n", self.message[len(self.header):])
                    if matchTransferEnd:
                        self.ok = True
                        break
                    proc_debug("Readbody ch")
                    chunk = stream.recv(BUF_SIZE)
                    if not chunk:
                        self.ok = False
                        break
                    self.message += chunk
            else:
                while 1:
                    bodycount += len(chunk)
                    if bodycount == contentLength:
                        self.ok = True
                        break
                    proc_debug("readbody cl")
                    if contentLength - bodycount >= BUF_SIZE:
                        chunk = stream.recv(BUF_SIZE)
                    else:
                        chunk = stream.recv(contentLength - bodycount)
                    if not chunk:
                        self.ok = False
                        break
                    self.message += chunk
        except OSError as value:
                proc_error("Message read failed (2) ")
                proc_error(str(value))
                self.ok = False
                self.timeout = not self.message
                      
def set_keep_alive(message, size, keep_alive):
    """Insert Connection: keep-alive header into existing message string

    size - int, search length
    keep_alive - bool, if False insert "Close" 
    """

    search_in = message[:size]
    matchConn = re.search(b"^connection:\s+.*$", search_in, re.IGNORECASE | re.MULTILINE)
    if matchConn:
        """

        ENSURE \\r!!!

        """
        return message[:matchConn.start()] + b"connection: " + (b"keep-alive" if keep_alive else b"close") + message[matchConn.end():]
    else:
        return message
