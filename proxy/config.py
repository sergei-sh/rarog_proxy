
import configparser
import sys

#singleton config object
class Config:
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

    
