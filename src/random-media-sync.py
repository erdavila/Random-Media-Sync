#!/usr/bin/env python
import sys
import os
import re
import random
import shutil
from optparse import OptionParser
from collections import namedtuple



MediaItem = namedtuple('MediaItem', 'type,path,size')



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
    return MediaItem(type='FILE', path=file_rel_path, size=file_size)


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
        return MediaItem(type='ALBUM', path=album_rel_path, size=total_size)
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


def fmt_bytesize(value):
    BYTE = 'B'
    
    original_value = value
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
    
    return '%d (%s)' % (original_value, alts[-1])


def delete(base_path, item_relpath):
    full_path = os.path.join(base_path, item_relpath)
    if os.path.isdir(full_path):
        shutil.rmtree(full_path)
    else:
        os.remove(full_path)
    
    # Delete  empty directories
    while '/' in item_relpath:
        (item_relpath, _) = os.path.split(item_relpath)
        full_path = os.path.join(base_path, item_relpath)
        
        if len(os.listdir(full_path)) == 0:
            debug('Deleting empty dir:', item_relpath)
            os.rmdir(full_path)
        else:
            # Not empty
            break


def copy(src_dir, dst_dir, item_path):
    src = os.path.join(src_dir, item_path)
    dst = os.path.join(dst_dir, item_path)
    
    if os.path.isdir(src):
        if os.path.isdir(dst):
            remove(dst)
        shutil.copytree(src, dst, ignore=ignore_non_media)
    else:
        dir, _ = os.path.split(dst)
        if not os.path.isdir(dir):
            os.makedirs(dir)
        shutil.copy(src, dst)


def ignore_non_media(dirpath, contents):
    ignored = []
    for item in contents:
        full_path = os.path.join(dirpath, item)
        _, ext = os.path.splitext(item)
        if os.path.isfile(full_path) and not is_media_ext(ext):
            ignored.append(item)
    return ignored


def parse_percent(value):
    if value[-1] == "%":
        return float(value[:-1])
    else:
        raise ValueError()


def parse_target_free(free_target):
    """
    The value of free_target must be a percentage or a byte size.
    Valid values: "10.5%", "1%", "567", "9B", "1023kB", "57.3Mb", "999GiB" 
    """
    try:
        return parse_percent(free_target), True
    except ValueError:
        pass
    
    m = re.search(r'^(\d+(?:\.\d+)?)([kmg]i?|)b?$', free_target, re.IGNORECASE)
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
            
        return val, False
    
    return int(free_target), False


def parse_keep(keep):
    """
    The value of keep must be a percentage or a count.
    Example of valid values: "10.5%", "1%", "567"
    Example of invalid values: "10 %", "1 %", "567", "abc"
    """
    try:
        return parse_percent(keep), True
    except ValueError:
        return int(keep), False


def parse_args():
    parser = OptionParser(usage="Usage: %prog [options] SOURCE DESTINATION TARGET_FREE")
    parser.add_option("-k", "--keep", dest="keep", metavar="KEEP", default="0",
                      help="minimum number of items currently in DESTINATION that will be kept")
    parser.add_option("-n", "--dry-run", action="store_true", default=False,
                      help="do not delete or copy anything")
    parser.add_option("--delete-only-in-dst", action="store_true", default=False,
                      help="delete media found in the destination which are not in the src_dir. ARE YOU SURE YOU WANT TO DO THIS?!")
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose", default=False,
                      help="verbose mode")
    (options, args) = parser.parse_args()
    
    if len(args) != 3:
        parser.error("Incorrect number of arguments")
    
    src_dir = args[0]
    dst_dir = args[1]
    options.device_free_target, options.device_free_target_is_percent = parse_target_free(args[2])
    options.keep, options.keep_is_percent = parse_keep(options.keep)
    
    global DEBUG
    DEBUG = options.verbose
    
    if options.dry_run:
        global delete, copy
        def _do_nothing(*args): pass
        delete = copy = _do_nothing
    
    return src_dir, dst_dir, options


def sorted_media(media):
    return sorted(media, key=str.upper)


class MediaWithSize(object):
    def __init__(self):
        self.items = {}
        self.size = 0
    
    def __len__(self):
        return len(self.items)
    
    def __iter__(self):
        return iter(self.items)
    
    def __setitem__(self, key, value):
        if key in self.items:
            self.size -= self.items[key].size
        self.items[key] = value
        self.size += value.size
    

def move_media(path, from_, to):
    item = from_.pop(path)
    to[path] = item


def process_media_in_dst_only(src, dst, dst_dir, must_delete):
    """
    Finds media in the destination which are not in the source.
    If the must_delete parameter is True, then the media is deleted.
    Remove the media from dst.
    """
    deleted_media = {}
    
    in_dst_only = set(dst) - set(src)
    if in_dst_only:
        if must_delete:
            print 'Deleting the following items in the destination directory that are not in the source directory:'
            def f(path):
                delete(dst_dir, path)
        else:
            print 'The following items in the destination directory will be ignored because they are not in the source directory:'
            def f(path):
                pass
        
        for path in sorted_media(in_dst_only):
            print "\t", path
            f(path)
            move_media(path, dst, deleted_media)
        
        print
    
    return deleted_media


def process_kept_media(src, dst, keep_count):
    src_kept = {}
    dst_kept = {}
    
    while len(dst_kept) < keep_count and len(dst) > 0:
        chosen = random.choice(dst.keys())
        move_media(chosen, src, src_kept)
        move_media(chosen, dst, dst_kept)
    
    if len(dst_kept) > 0:
        print 'Keeping %d items' % len(dst_kept)
        print
    
    return dst_kept


def select_media(src, src_selected_size_target):
    src_selected = MediaWithSize()
    
    while src_selected.size < src_selected_size_target and len(src) > 0:
        chosen = random.choice(src.keys())
        move_media(chosen, src, src_selected)
    
    return src_selected


def delete_media(src_selected, dst, dst_dir):
    for num, item in enumerate(sorted_media(dst), 1):
        if item not in src_selected:
            print 'Deleting (%d/%d): %s' % (num, len(dst), item)
            delete(dst_dir, item)
        else:
            print 'Keeping (%d/%d): %s' % (num, len(dst), item)


def copy_media(src_selected, dst, src_dir, dst_dir):
    for num, path  in enumerate(sorted_media(src_selected), 1):
        if path not in dst:
            print 'Copying (%d/%d): %s' % (num, len(src_selected), path)
            copy(src_dir, dst_dir, path)


def main():
    src_dir, dst_dir, options = parse_args()
    
    print 'Scanning source: %s' % src_dir
    src = dict((item.path, item) for item in scan_media_dir(src_dir))
    print "%d items found" % len(src)
    
    print
    
    print 'Scanning destination: %s' % dst_dir
    dst = dict((item.path, item) for item in scan_media_dir(dst_dir))
    print "%d items found" % len(dst)
    
    print
    
    
    process_media_in_dst_only(src, dst, dst_dir, options.delete_only_in_dst)
    
    
    if options.keep_is_percent:
        keep_count = len(dst) * options.keep / 100
    else:
        keep_count = options.keep
    debug(keep_count=keep_count, len__dst=len(dst))
    
    process_kept_media(src, dst, keep_count)
    
    
    vfsstat = os.statvfs(dst_dir)
    if options.device_free_target_is_percent:
        device_total = vfsstat.f_bsize * vfsstat.f_blocks
        debug(device_total=fmt_bytesize(device_total))
        device_free_target = device_total * options.device_free_target / 100
    else:
        device_free_target = options.device_free_target
    
    device_free_current = vfsstat.f_bsize * vfsstat.f_bavail
    dst_size = sum(item.size for item in dst.itervalues())
    src_selected_size_target = dst_size + device_free_current - device_free_target
    
    debug(device_free_target=fmt_bytesize(device_free_target))
    debug(device_free_current=fmt_bytesize(device_free_current))
    debug(dst_size=fmt_bytesize(dst_size))
    debug(src_selected_size_target=fmt_bytesize(src_selected_size_target))
    
    src_selected = select_media(src, src_selected_size_target)
    
    
    delete_media(src_selected, dst, dst_dir)
    
    
    copy_media(src_selected, dst, src_dir, dst_dir)
    
    if DEBUG:
        vfsstat = os.statvfs(dst_dir)
        device_free_current = vfsstat.f_bsize * vfsstat.f_bavail
        debug(device_free_current=fmt_bytesize(device_free_current))


def debug(*args, **kwargs):
    if DEBUG:
        args_msg = ' '.join(str(arg) for arg in args)
        kwargs_msg = ', '.join(key + ' = ' + str(val) for key, val in kwargs.iteritems())
        print ">>>", args_msg + kwargs_msg


if __name__ == '__main__':
    main()
