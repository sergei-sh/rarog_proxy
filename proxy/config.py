""" 
Updated: 2016
Author: Sergei Shliakhtin
Contact: xxx.serj@gmail.com
Notes: TO BE REWRITTEN (no need for singleton)
"""


import configparser
import sys

class Config:
    """Wrap ConfigParser to ease access to "proxy.ini" """
    class ConfigLoader(configparser.ConfigParser):
        def __init__(self):
            super(self.__class__, self).__init__()
            if 0 == len(self.read('proxy.ini')):
                sys.exit('Need proxy.ini to run')

    _config = ConfigLoader()

    @staticmethod
    def value(section, key):
        return Config._config.get(section, key)

    def __call__(self):
        return Config._config

    
