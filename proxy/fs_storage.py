""" 
Updated: 2016
Author: Sergei Shliakhtin
Contact: xxx.serj@gmail.com
Notes: Filesystem storage for cached data
"""


import fcntl
import os

from proxy.config import Config
from proxy.encoding import to_str, to_bytes
from proxy.logger import proc_error
from proxy.const import Const

import multiprocessing

class LockedFile():
    """The wrapper which puts an advisory lock on an opened file object and removes it
       upon context exit as well as closes the file"""
    def __init__(self, ofile, fcntl_flags):
#        super(self.__class__, self).__init__(ofile)
        self._file = ofile;
        self._flags = fcntl_flags

    def __enter__(self):
        try:
            fcntl.flock(self._file.fileno(), self._flags | fcntl.LOCK_NB)
        except OSError:
            locked = True
            
        fcntl.flock(self._file.fileno(), self._flags)

        return self._file
    
    def __exit__(self, exc_type, exc_value, traceback):
        fcntl.flock(self._file.fileno(), fcntl.LOCK_UN)
        self._file.close()

class FSStorage:
    def __init__(self):
        self.__cache_dir = to_bytes(Config.value(Const.STORAGE_SECTION, 'cache_path'))
        assert self.__cache_dir

    def _amend_path(self, path):
        return os.path.join(self.__cache_dir, path)

    def save(self, key_path, data):
        key_path = self._amend_path(key_path)
        cacheDir, file = os.path.split(key_path)
        MAX_NAME = 255
        if len(os.path.basename(key_path)) > MAX_NAME:
            return False
        try: 
            if not os.path.exists(cacheDir):
                os.makedirs(cacheDir, mode=0o777, exist_ok=True)

            with LockedFile(open(key_path, "wb"), fcntl.LOCK_EX | fcntl.LOCK_NB) as cacheFile: 
                cacheFile.write(data)
            return True
        except FileExistsError:
            return False
        except OSError as errv:
            proc_error("Couldn't save to %s : %s" % (key_path, str(errv)))
            return False

    def fetch(self, key_path):
        try:
            key_path = self._amend_path(key_path)
            with LockedFile(open(key_path, "rb"), fcntl.LOCK_SH) as cacheFile:
                return cacheFile.read()
        except OSError as errv:
            log("%s file read error: %s" % (key_path, str(errv)))
            return None


    def haskey_time(self, key_path): 
        key_path = self._amend_path(key_path)
        if os.path.isfile(key_path):
            time_sec = os.path.getmtime(key_path)
            return True, time_sec
        return False, None 

    def erase(self, key_path):
        key_path = self._amend_path(key_path)
        try:
            os.remove(key_path)
        except OSError as errv:
            log("Couldn't remove file %s : %s" % (key_path, str(errv)))
            return
        try:
            key_path = os.path.dirname(key_path)
            os.removedirs(key_path)
        except OSError as errv:
            if os.errno.ENOTEMPTY == errv.errno:
                return
            log("Couldn't remove dir %s : %s" % (key_path, str(errv)))


