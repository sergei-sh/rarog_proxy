""" 
Updated: 2016
Author: Sergei Shliakhtin
Contact: xxx.serj@gmail.com
Notes:
"""


import re

from proxy.logger import proc_error
from proxy.message_reader import MessageReader

class ResponseReader(MessageReader):
    """Extracts response's fields of interest
    """

    def __init__(self, stream):
        """Get incoming bytes, read as long as needed and split into desired fields

        stream - open socket to read from
        """
        MessageReader.__init__(self, stream)
        self.response_status = 0 
        self.response_data = b""

        if not self.ok:
            return

        match = re.search(b"(\r\n|\n)", self.message)
        if not match:
            proc_error("Bad response (1)")
            proc_error(self.message)
            return
        self.response_data = self.message[match.end():]
        status = self.message[:match.start()]
        try:
            statusParts = status.split(b" ", 2)
            self.response_status = int(statusParts[1])
        except IndexError:
            proc_error("Bad response (2)")
            

