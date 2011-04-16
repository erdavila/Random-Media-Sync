import os.path

from rms.media import Media


def scan_media_dir(media_dir):
    for item in sorted(os.listdir(media_dir), key=str.upper):
        item_path = os.path.join(media_dir, item)
        if os.path.isfile(item_path):
            f = scan_file(media_dir, item)
            if f is not None:
                yield f
        elif os.path.isdir(item_path):
            for artist_item in scan_artist_dir(media_dir, item):
                yield artist_item


def scan_file(media_dir, file_rel_path):
    _, ext = os.path.splitext(file_rel_path)
    
    if not is_media_ext(ext):
        return None
    
    file_path = os.path.join(media_dir, file_rel_path)
    file_size = os.path.getsize(file_path)
    return Media.Item(type='FILE', path=file_rel_path, size=file_size)


def scan_artist_dir(media_dir, artist_rel_path):
    artist_path = os.path.join(media_dir, artist_rel_path)
    for item in sorted(os.listdir(artist_path), key=str.upper):
        item_path = os.path.join(artist_path, item)
        if os.path.isfile(item_path):
            f = scan_file(media_dir, os.path.join(artist_rel_path, item))
            if f is not None:
                yield f
        elif os.path.isdir(item_path):
            a = scan_album_dir(media_dir, os.path.join(artist_rel_path, item))
            if a is not None:
                yield a
        

def scan_album_dir(media_dir, album_rel_path):
    album_path = os.path.join(media_dir, album_rel_path)
    
    total_size = 0
    for (path, _, files) in os.walk(album_path):
        for file in files:
            _, ext = os.path.splitext(file)
            if is_media_ext(ext):
                filepath = os.path.join(path, file)
                total_size += os.path.getsize(filepath)
    
    if total_size:
        return Media.Item(type='ALBUM', path=album_rel_path, size=total_size)
    else:
        return None


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
