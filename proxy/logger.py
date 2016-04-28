
import logging
import logging.config
import multiprocessing
import os

from proxy.const import Const

def log_basic_config():
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

def logerror(message):
    log(message)
    log_per_process(message, "err_")

def logstate(message):
    log_per_process(message, "state_")

def logrequest(message):
    log_per_process(message, "req_")

def log_per_process(message, prefix):
    logger_name = prefix + multiprocessing.current_process().name
    if not prefix in logstate.has_handler:
        logstate.has_handler.append(prefix)
        if not os.path.exists(Const.LOG_DIR):
            os.makedirs(Const.LOG_DIR, mode=0o777, exist_ok=True)
        fhandler = logging.FileHandler(os.path.join(Const.LOG_DIR, logger_name), "w")
        fhandler.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%H:%M:%S"))
        logger(logger_name).addHandler(fhandler)
    logger(logger_name).warning(message)

logstate.has_handler = [] 


