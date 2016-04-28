
def to_str(data):
    if isinstance(data, bytes):
        return data.decode("utf-8")
    else:
        return data

def to_bytes(data):
    if isinstance(data, str):
        return data.encode("utf-8")
    else:
        return data


