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
    
    return alts[-1]


def fmt_percent(value, out_of):
    return '%.1f%%' % (100.0 * value / out_of)


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
    parser = OptionParser(usage="Usage: %prog [options] SOURCE DESTINATION TARGET_FREE",
                          description="""SOURCE and DESTINATION are directories.
                              TARGET_FREE is the amount of space that will be kept
                              unused in the target device. It can be a percentage
                              ("50%", "0%", "25.7%", etc.) or a byte-size value ("1gb",
                              "2.5GiB", "10mB", etc.).""")
    parser.add_option("-k", "--keep", dest="keep", metavar="KEEP", default="0",
                      help="""Minimum number of items currently in DESTINATION
                          that will be kept. It can be a percentage (see 
                          TARGET_FREE argument above) or an absolute number of items.""")
    parser.add_option("-n", "--dry-run", action="store_true", default=False,
                      help="Do not delete or copy anything.")
    parser.add_option("--delete-only-in-dst", action="store_true", default=False,
                      help="Delete media found in the destination which are not in the src_dir. ARE YOU SURE YOU WANT TO DO THIS?!")
    (options, args) = parser.parse_args()
    
    if len(args) != 3:
        parser.error("Incorrect number of arguments")
    
    src_dir = args[0]
    dst_dir = args[1]
    options.device_free_target, options.device_free_target_is_percent = parse_target_free(args[2])
    options.keep, options.keep_is_percent = parse_keep(options.keep)
    
    if options.dry_run:
        global delete, copy
        def _do_nothing(*args): pass
        delete = copy = _do_nothing
    
    return src_dir, dst_dir, options


def sorted_media(media):
    return sorted(media, key=str.upper)


class MediaWithSize(dict):
    def __init__(self, *args, **kwargs):
        super(MediaWithSize, self).__init__(*args, **kwargs)
        self.size = sum(value.size for value in self.itervalues())
    
    def __setitem__(self, key, value):
        if key in self:
            previous = self[key]
            has_previous = True
        else:
            has_previous = False
        
        super(MediaWithSize, self).__setitem__(key, value)
        
        if has_previous:
            self.size -= previous.size
        
        self.size += value.size
    
    def __delitem__(self, key):
        if key in self:
            previous = self[key]
            has_previous = True
        else:
            has_previous = False
        
        super(MediaWithSize, self).__delitem__(key)
        
        if has_previous:
            self.size -= previous.size
    
    def pop(self, key, *args):
        try:
            value = super(MediaWithSize, self).pop(key)
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
        (key, value) = super(MediaWithSize, self).popitem()
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
    

def move_media(path, from_, to):
    item = from_.pop(path)
    to[path] = item


def partition_media(from_, to):
    """Move to a new set every media in from_ that is not in to"""
    difference = MediaWithSize()
    for item in from_.keys():
        if item not in to:
            move_media(item, from_, difference)
    return difference


def process_media_in_dst_only(src, dst, dst_dir, must_delete):
    """
    Finds media in the destination which are not in the source.
    If the must_delete parameter is True, then the media is deleted.
    Remove the media from dst.
    """
    dst_only = MediaWithSize()
    
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
            move_media(path, dst, dst_only)
        print "\tTotal: %s" % fmt_bytesize(dst_only.size)
        
        print
    
    return dst_only


def process_kept_media(src, dst, keep_count):
    src_kept = {}
    dst_kept = MediaWithSize()
    
    while len(dst_kept) < keep_count and len(dst) > 0:
        chosen = random.choice(dst.keys())
        move_media(chosen, src, src_kept)
        move_media(chosen, dst, dst_kept)
    
    return dst_kept


def select_media(src, src_selected_size_target):
    src_selected = MediaWithSize()
    
    while src_selected.size < src_selected_size_target and len(src) > 0:
        chosen = random.choice(src.keys())
        move_media(chosen, src, src_selected)
    
    return src_selected


def delete_media(src_selected, dst, dst_dir):
    dst_delete = partition_media(dst, src_selected)
    
    if dst_delete:
        print "Deleting %s" % fmt_bytesize(dst_delete.size)
        for num, item in enumerate(sorted_media(dst_delete), 1):
            print 'Deleting: %s' % item
            delete(dst_dir, item)
        print


def copy_media(src_selected, dst, src_dir, dst_dir):
    src_sel_copy = partition_media(src_selected, dst)
    
    if src_sel_copy:
        print "Copying %s" % fmt_bytesize(src_sel_copy.size)
        for num, path  in enumerate(sorted_media(src_sel_copy), 1):
            print 'Copying (%d/%d): %s' % (num, len(src_sel_copy), path)
            copy(src_dir, dst_dir, path)
        print
    
    return src_sel_copy


def main():
    src_dir, dst_dir, options = parse_args()
    
    print 'Scanning source: %s' % src_dir
    src = MediaWithSize((item.path, item) for item in scan_media_dir(src_dir))
    print "%d items found in %s" % (len(src), fmt_bytesize(src.size))
    
    print
    
    print 'Scanning destination: %s' % dst_dir
    dst = MediaWithSize((item.path, item) for item in scan_media_dir(dst_dir))
    print "%d items found in %s" % (len(dst), fmt_bytesize(dst.size))
    
    print
    
    
    process_media_in_dst_only(src, dst, dst_dir, options.delete_only_in_dst)
    
    
    vfsstat = os.statvfs(dst_dir)
    device_total = vfsstat.f_bsize * vfsstat.f_blocks
    device_free_current = vfsstat.f_bsize * vfsstat.f_bavail
    print "Total size of the destination device: %s" % fmt_bytesize(device_total)
    print "Media currently in the destination device: %s (%s)" % (fmt_bytesize(dst.size), fmt_percent(dst.size, device_total))
    print "Current free space in the destination device: %s (%s)" % (fmt_bytesize(device_free_current), fmt_percent(device_free_current, device_total))
    print
    
    
    if options.keep_is_percent:
        keep_count = len(dst) * options.keep / 100
    else:
        keep_count = options.keep
    
    dst_kept = process_kept_media(src, dst, keep_count)
    
    
    if options.device_free_target_is_percent:
        device_free_target = device_total * options.device_free_target / 100
    else:
        device_free_target = options.device_free_target
    
    src_selected_size_target = dst.size + device_free_current - device_free_target
    src_selected = select_media(src, src_selected_size_target)
    
    
    delete_media(src_selected, dst, dst_dir)
    
    
    src_sel_copy = copy_media(src_selected, dst, src_dir, dst_dir)
    

    vfsstat = os.statvfs(dst_dir)
    device_total = vfsstat.f_bsize * vfsstat.f_blocks
    device_free_current = vfsstat.f_bsize * vfsstat.f_bavail
    dst_media_size = dst.size + dst_kept.size + src_sel_copy.size
    print "Total size of the destination device: %s" % fmt_bytesize(device_total)
    print "Media in the destination device: %s (%s)" % (fmt_bytesize(dst_media_size), fmt_percent(dst_media_size, device_total))
    print "Free space in the destination device: %s (%s)" % (fmt_bytesize(device_free_current), fmt_percent(device_free_current, device_total))


if __name__ == '__main__':
    main()
