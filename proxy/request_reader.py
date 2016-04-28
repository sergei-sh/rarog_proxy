
from proxy.message_reader import MessageReader

class RequestReader(MessageReader):
    """Extracts request fields of interest"""
    GET, OTHER, BAD = list(range(3))    

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
        self._method = RequestReader.BAD
        self._hostname = b""

        requestParts = self.message().split()
        if not self.ok() or len(requestParts) < 2:
            self._method = RequestReader.BAD
            return

        self._method = RequestReader.GET if b"GET" == requestParts[0] else RequestReader.OTHER
        URI = requestParts[1]
        version = requestParts[2]

        if URI.startswith(b"http://"):
            URI = URI.replace(b"http://",b"",1)

        # strip off any leading slashes in URI                                                       
       	URI = URI.lstrip(b"/")
        # remove parent directory changes - security                                                 
        URI = URI.replace(b"/..",b"")
        self._uri = URI
        # split hostname from resource                                                               
        resourceParts = URI.split(b"/",1)
        self._hostname = resourceParts[0]
        resource = b"/"

        if len(resourceParts) == 2:
            resource = resource + resourceParts[1]
        self._cache_location = self._hostname + resource

        if self._cache_location.endswith(b"/"):
        	self._cache_location = self._cache_location + b"default"

 
