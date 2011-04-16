import re


def parse_percent(value):
    if value[-1] == "%":
        return float(value[:-1])
    else:
        raise ValueError()


def parse_bytesize(value):
    """Example of valid values: "10.5%", "1%", "567", "9B", "1023kB", "57.3Mb", "999GiB"
    """
    m = re.search(r'^(\d+(?:\.\d+)?)([kmg]i?|)b?$', value, re.IGNORECASE)
    if m is not None:
        val = float(m.group(1))
        multiplier = m.group(2).lower()
        if multiplier != '':
            val *= 1024
            if multiplier != 'k':
                val *= 1024
                if multiplier != 'm':
                    assert multiplier == 'g'
                    val *= 1024
            
        return val
    else:
        raise ValueError()


def format_bytesize(value):
    BYTE = 'B'
    
    alts = []
    for suffix in ('ki', 'Mi', 'Gi'):
        abs_value = abs(value)
        if abs_value < 1024: break
        
        v = value / 1024.0
        if abs_value % 1024 == 0:
            alt = '%d' % v
        else:
            alt = '~%.1f' % v
        alts.append(alt + suffix + BYTE)
        
        value = v
    
    if not alts:
        alts.append(str(value) + BYTE)
    
    return alts[-1]


def format_percent(value, out_of):
    return '%.1f%%' % (100.0 * value / out_of)
