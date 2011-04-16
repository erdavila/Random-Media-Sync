from collections import namedtuple



class Media(dict):
    Item = namedtuple('MediaItem', 'type,path,size')

    
    
    def __init__(self, *args, **kwargs):
        super(Media, self).__init__(*args, **kwargs)
        self.size = sum(value.size for value in self.itervalues())
    
    def __setitem__(self, key, value):
        if key in self:
            previous = self[key]
            has_previous = True
        else:
            has_previous = False
        
        super(Media, self).__setitem__(key, value)
        
        if has_previous:
            self.size -= previous.size
        
        self.size += value.size
    
    def __delitem__(self, key):
        if key in self:
            previous = self[key]
            has_previous = True
        else:
            has_previous = False
        
        super(Media, self).__delitem__(key)
        
        if has_previous:
            self.size -= previous.size
    
    def pop(self, key, *args):
        try:
            value = super(Media, self).pop(key)
        except KeyError:
            if args:
                (default,) = args
                return default
            else:
                raise KeyError()
        else:
            self.size -= value.size
            return value
    
    def popitem(self):
        (key, value) = super(Media, self).popitem()
        self.size -= value.size
        return (key, value)
    
    def setdefault(self, key, default=None):
        if key in self:
            return self[key]
        else:
            self.__setitem__(key, default)
            return default
    
    def update(self, *args, **kwargs):
        raise NotImplementedError()
