""" 
Updated: 2016
Author: Sergei Shliakhtin
Contact: xxx.serj@gmail.com
Notes: Storage indirection level
"""


from proxy import ProxyException
from proxy.config import Config
from proxy.const import Const 

def get_storage():
    """
    
    return - Storage object of certain type depending on config setting
    """

    storage_type = Config.value(Const.STORAGE_SECTION, "storage")
    if "DB" == storage_type:
        from proxy.db_storage import DBStorage
        DBStorage.check_init_db()
        return DBStorage()
    elif "FS" == storage_type:
        from proxy.fs_storage import FSStorage
        return FSStorage()
    else:
        raise ProxyException('Need either DB or FS storage type in proxy.ini')
