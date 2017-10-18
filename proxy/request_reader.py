""" 
Updated: 2016
Author: Sergei Shliakhtin
Contact: xxx.serj@gmail.com

Only GET and CONNECT methods are currently supported
"""

from proxy.message_reader import MessageReader

class RequestReader(MessageReader):
    """Gets already received message and splits into fields of interest
    """
    GET, CONNECT, OTHER = list(range(3))    
    
    def __init__(self, stream, pipeline_tail=b""):
        """ Get incoming bytes, read as long as needed and split into desired fields

        stream - open socket to read from
        pipeline_tail - bytes from this request, already read as the tail of 
            previous message
        """
        # read message from stream
        MessageReader.__init__(self, stream,  pipeline_tail)

        self.cache_location = b""
        self.hostname = b""
        
        req_parts = self.message.split()
        if not self.ok or len(req_parts) < 2:
            self.method = RequestReader.OTHER
            return

        if b"GET" == req_parts[0]:
            self.method = RequestReader.GET 
        elif b"CONNECT" == req_parts[0]: 
            self.method = RequestReader.CONNECT
        else:
            self.method = RequestReader.OTHER

        self.method_str = req_parts[0]
        uri = req_parts[1]
        version = req_parts[2]
        
        if uri.startswith(b"https://"):
            # To connect through an HTTP proxy with HTTPS neeed to issue CONNECT method
            # Reply Error 501
            self.method = RequestReader.OTHER
            return

        if uri.startswith(b"http://"):
            uri = uri.replace(b"http://", b"", 1)

        # strip off any leading slashes in URI                                                       
       	uri = uri.lstrip(b"/")
        # remove parent directory changes - security                                                 
        uri = uri.replace(b"/..",b"")
        self.uri = uri
        # split hostname from resource                                                               
        resource_parts = uri.split(b"/",1)
        self.hostname = resource_parts[0]
        resource = b"/"

        if len(resource_parts) == 2:
            resource = resource + resource_parts[1]
        self.cache_location = self.hostname + resource

        if self.cache_location.endswith(b"/"):
        	self.cache_location = self.cache_location + b"default"

 
