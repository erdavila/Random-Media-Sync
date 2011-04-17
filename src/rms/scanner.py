from itertools import chain
import os.path

from rms.media import Media


MEDIA_EXTS = (
    '.mid',
    '.mp3',
    '.ogg',
    '.wav',
    '.wma',
)
def is_media_ext(ext):
    ext = ext.lower()
    return ext in MEDIA_EXTS


class Scanner(object):
    def __init__(self, ignore, forced_albums, not_albums):
        self.ignore = ignore
        self.forced_albums = forced_albums
        self.not_albums = not_albums
    
    def is_album(self, dir_relpath):
        return dir_relpath in self.forced_albums
    
    def is_not_album(self, dir_relpath):
        return dir_relpath in self.not_albums
    
    def scan(self, media_dir):
        """Returns a Media object."""
        items = self.scan_dir(media_dir, '', level=0)
        return Media((item.relpath, item) for item in items)
    
    def scan_dir(self, media_dir, dir_relpath, level):
        """Returns a generator of Media.Item objects"""
        if dir_relpath in self.ignore:
            #print ">>> Ignoring:", dir_relpath
            return ()
        
        if level < 2:
            # Root or artist dir
            if self.is_album(dir_relpath):
                #print ">>> Forced album:", dir_relpath
                return self.scan_album(media_dir, dir_relpath)
            else:
                gens = self.scan_not_album(media_dir, dir_relpath, level)
                return chain.from_iterable(gens)
        else:
            # Album dir
            if self.is_not_album(dir_relpath):
                #print ">>> Forced not-album:", dir_relpath
                gens = self.scan_not_album(media_dir, dir_relpath, level)
                return chain.from_iterable(gens)
            else:
                return self.scan_album(media_dir, dir_relpath)
    
    def scan_file(self, media_dir, file_relpath):
        """Generator of Media.Item file objects."""
        if file_relpath in self.ignore:
            #print ">>> Ignoring:", file_relpath
            return
        
        _, ext = os.path.splitext(file_relpath)
        
        if is_media_ext(ext):
            file_fullpath = os.path.join(media_dir, file_relpath)
            file_size = os.path.getsize(file_fullpath)
            yield Media.Item(type='FILE', relpath=file_relpath, size=file_size)
    
    def scan_album(self, media_dir, album_relpath):
        """Generator of a Media.Item album object."""
        album_fullpath = os.path.join(media_dir, album_relpath)
        
        total_size = 0
        for (dir_fullpath, _, files) in os.walk(album_fullpath):
            for file in files:
                _, ext = os.path.splitext(file)
                if is_media_ext(ext):
                    file_fullpath = os.path.join(dir_fullpath, file)
                    total_size += os.path.getsize(file_fullpath)
        
        if total_size:
            yield Media.Item(type='ALBUM', relpath=album_relpath, size=total_size)
    
    def scan_not_album(self, media_dir, dir_relpath, level):
        """Generator of generators of Media.Item objects."""
        full_path = os.path.join(media_dir, dir_relpath)
        for item in os.listdir(full_path):
            item_fullpath = os.path.join(full_path, item)
            item_relpath = os.path.join(dir_relpath, item)
            if os.path.isfile(item_fullpath):
                gen = self.scan_file(media_dir, item_relpath)
                yield gen
            elif os.path.isdir(item_fullpath):
                gen = self.scan_dir(media_dir, item_relpath, level + 1)
                yield gen
