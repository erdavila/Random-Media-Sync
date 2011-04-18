
ENABLED = False


def log(*args, **kwargs):
    if ENABLED:
        print ' '.join(args), ', '.join(key + ' = ' + repr(value) for key, value in kwargs.iteritems())
