""" 
Updated: 2016
Author: Sergei Shliakhtin
Contact: xxx.serj@gmail.com
Notes: Logging helpers
"""


import logging
import logging.config
import multiprocessing
import os

from proxy.const import Const
from proxy.config import Config

def log_basic_config():
    """Init loggefs from file config. Should be called once only"""
    #logging.basicConfig(format="%(message)s", level=logging.INFO)
    logging.config.fileConfig("loggers.conf")
    console = logger(Const.CONSOLE_LOGGER)
    for handler in console.handlers:
        if isinstance(handler, logging.StreamHandler):
            handler.terminator = ""

__per_process_lock = None

def init_lock(lock):
    global __per_process_lock
    __per_process_lock = lock

def logger(label):
    return logging.getLogger(label)

def log(message, level=logging.INFO, label=None):  
    if None == label:
        label = Const.CONSOLE_LOGGER 

    PROTECTED_STDOUT = False
    global __per_process_lock
    if __per_process_lock and PROTECTED_STDOUT:
        with __per_process_lock:
            logger(label).log(level, message)
    else:
        logger(label).log(level, message)

def proc_error(message):
    log(message)
    log_per_process(message, "err_")

def proc_state(message):
    log_per_process(message, "state_")

def proc_debug(message):
    proc_state(message)    

def log_per_process(message, prefix):
    logger_name = prefix + multiprocessing.current_process().name
    if not prefix in proc_state.has_handler:
        proc_state.has_handler.append(prefix)
        log_dir = Config.value(Const.MAIN_SECTION, "log_path")
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, mode=0o777, exist_ok=True)
        fhandler = logging.FileHandler(os.path.join(log_dir, logger_name), "w")
        fhandler.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%H:%M:%S"))
        logger(logger_name).addHandler(fhandler)
    logger(logger_name).warning(message)

proc_state.has_handler = [] 


