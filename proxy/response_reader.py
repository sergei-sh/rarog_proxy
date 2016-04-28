
import re

from proxy.logger import logerror
from proxy.message_reader import MessageReader

class ResponseReader(MessageReader):
    """Extracts response's fields of interest"""

    def response_status(self):
        return self._response_status 

    def response_data(self):
        return self._response_data

    def __init__(self, stream):
        MessageReader.__init__(self, stream)
        self._response_status = 0 
        self._response_data = b""

        if not self._ok:
            return

        match = re.search(b"(\r\n|\n)", self.message())
        if not match:
            logerror("Bad response (1)")
            logerror(self.message())
            return
        self._response_data = self.message()[match.end():]
        status = self.message()[:match.start()]
        try:
            statusParts = status.split(b" ", 2)
            self._response_status = int(statusParts[1])
        except:
            logerror("Bad response (2)")
            

