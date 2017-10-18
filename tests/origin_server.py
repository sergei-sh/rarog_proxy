""" 
Updated: 2016
Author: Sergei Shliakhtin
Contact: xxx.serj@gmail.com
Parser: Python 2.7
Notes:

Used this for proxy_mult functional testing. This module is intended to be run directly
from the command line
"""

from collections import namedtuple

import re
import time
import socketserver 
import http.server 
import urllib
import sys

PORT = 8000

Response = namedtuple("Response", ["code", "body"])
responses = {
    "/resource1" : Response(200, "ResponseBody1"),
    "/resource2" : Response(200, "ResponseBody2"),
}

class Server(http.server.SimpleHTTPRequestHandler):
    """Http server sending back predefined responses for certain requests"""

    def do_GET(self):
        print("Server: handling path: ", self.path)
        try:
            """ Since request is sent through proxy, resource is the full URL"""
            path = re.match(r"http://[^/]+(/.*)", self.path).group(1)
            resp = responses[path]
        except (KeyError, AttributeError):
            resp = Response(404, "")
        self.send_response(resp.code)
        self.send_header('Content-type','text/html')
        body = resp.body.encode("ascii", errors="ignore")
        self.send_header("Content-length", str(len(body)))

        self.end_headers()
        self.wfile.write(body)

def run():
    socketserver.ForkingTCPServer.allow_reuse_address = True
    httpd = socketserver.ForkingTCPServer(('', PORT), Server)
    print("Serving at port", PORT)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("Origin server: KeyboardInterrupt")        

run()    
