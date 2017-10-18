    
def _response(status_line):
    """ Given status line compose valid response message"""
    return b"HTTP/1.1 " + status_line + b"\nContent-length: 0\n\n"

RESPONSE_400 = _response(b"400 Bad Request")
RESPONSE_408 = _response(b"408 Request Timeout")
RESPONSE_500 = _response(b"500 Internal Server Error")
RESPONSE_502 = _response(b"502 Bad Gateway")
RESPONSE_504 = _response(b"504 Gateway Timeout")
RESPONSE_501 = _response(b"501 Not Implemented")
RESPONSE_200 = _response(b"200 OK")

def add_ok_status(headers_body):
    return b"HTTP/1.1 200 OK\n" + headers_body
