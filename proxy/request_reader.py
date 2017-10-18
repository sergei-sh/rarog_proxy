""" 
Updated: 2016
Author: Sergei Shliakhtin
Contact: xxx.serj@gmail.com
Notes: Very limited request parsing. Only GET method is supported
"""


from proxy.message_reader import MessageReader

class RequestReader(MessageReader):
    """Extracts request fields of interest
    """
    GET, CONNECT, OTHER = list(range(3))    

    def cache_location(self):
        return self._cache_location

    def method(self):
        return self._method

    def hostname(self):
        return self._hostname
    
    def uri(self):
        return self._uri

    def __init__(self, stream, pipeline_tail=b""):
        MessageReader.__init__(self, stream,  pipeline_tail)
        self._cache_location = b""
        self._hostname = b""
        
        req_parts = self.message().split()
        if not self.ok() or len(req_parts) < 2:
            self._method = RequestReader.OTHER
            return

        if b"GET" == req_parts[0]:
            self._method = RequestReader.GET 
        elif b"CONNECT" == req_parts[0]: 
            self._method = RequestReader.CONNECT
        else:
            self._method = RequestReader.OTHER

        self.method_str = req_parts[0]
        uri = req_parts[1]
        version = req_parts[2]
        
        if uri.startswith(b"https://"):
            # To connect through an HTTP proxy with HTTPS neeed to issue CONNECT method
            # Reply Error 501
            self._method = RequestReader.OTHER
            return

        if uri.startswith(b"http://"):
            uri = uri.replace(b"http://", b"", 1)

        # strip off any leading slashes in URI                                                       
       	uri = uri.lstrip(b"/")
        # remove parent directory changes - security                                                 
        uri = uri.replace(b"/..",b"")
        self._uri = uri
        # split hostname from resource                                                               
        resource_parts = uri.split(b"/",1)
        self._hostname = resource_parts[0]
        resource = b"/"

        if len(resource_parts) == 2:
            resource = resource + resource_parts[1]
        self._cache_location = self._hostname + resource

        if self._cache_location.endswith(b"/"):
        	self._cache_location = self._cache_location + b"default"

 
