""" 
Updated: 2016
Author: Sergei Shliakhtin
Contact: xxx.serj@gmail.com
Notes: String conversions
"""

def to_str(data):
    """Convert to string, whatever is passed.

    data - bytes: convert ascii -> Unicode; str: do nothing
    """
    if isinstance(data, bytes):
        return data.decode("ascii")
    else:
        return data

def to_bytes(data):
    """Convert to bytes, whatever is passed.

    data - bytes: do nothing; str: convert Unicode -> ascii
    """
    if isinstance(data, str):
        return data.encode("ascii", errors="ignore")
    else:
        return data


