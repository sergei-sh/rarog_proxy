""" 
Updated: 2017
Author: Sergei Shliakhtin
Contact: xxx.serj@gmail.com
Parser: Python 3
Notes: 

To be run from the same directory where proxy.py resides!
"""

from functools import partial
from multiprocessing import Process
import os
import requests
import signal
import subprocess as sup
from time import sleep
from unittest import TestCase

class RequestsFunctional(TestCase):

    def setUp(self):        
        # PORT: 127.0.0.1:8000
        print("Starting servers")
        self.orig_proc = sup.Popen(["python3", "tests/origin_server.py"], stderr=sup.STDOUT)
        self.proxy_proc = sup.Popen(["python3", "proxy.py", "127.0.0.1", "8008", "5"], stderr=sup.STDOUT)
        # Give servers some time to start. Strictly speaking it's unknown how log to wait
        # Better solution would be to anlyse STDOUT for started confirmation
        sleep(0.5)

        self.proxies = { "http" : "http://127.0.0.1:8008" }

    def tearDown(self):
        print("Stropping servers")
        self.proxy_proc.send_signal(signal.SIGINT)
        self.orig_proc.send_signal(signal.SIGINT)

    @classmethod
    def setUpClass(cls):
        pass

    @classmethod
    def tearDownClass(cls):
        pass

    def test_ok(self):
        r = requests.get("http://localhost:8000/resource1", proxies=self.proxies)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, "ResponseBody1")

    def test_not_found(self):
        r = requests.get("http://localhost:8000/resource_unknown", proxies=self.proxies)
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.text, "")

    def test_bad_gateway(self):
        self.orig_proc.send_signal(signal.SIGINT)
        r = requests.get("http://localhost:8000/resource1", proxies=self.proxies)
        self.assertEqual(r.status_code, 502)
        self.assertEqual(r.text, "")

    def test_not_implemented(self):
        r = requests.post("http://localhost:8000/resource1", data={}, proxies=self.proxies)
        self.assertEqual(r.status_code, 501)
        self.assertEqual(r.text, "")



             


