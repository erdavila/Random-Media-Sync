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
    
    alts = []
    for suffix in ('ki', 'Mi', 'Gi'):
        if value < 1024: break
        
        v = value / 1024.0
        if value % 1024 == 0:
            alt = '%d' % v
        else:
            alt = '~%.1f' % v
        alts.append(alt + suffix + BYTE)
        
        value = v
    
    if not alts:
        alts.append(str(value) + BYTE)
    
    return alts[-1]


def delete(path):
    if os.path.isdir(path):
        shutil.rmtree(path)
    else:
        os.remove(path)


def copy(src, dst):
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
        return int(value[:-1])
    else:
        raise ValueError()


def parse_target_free(target_free):
    """
    The value of target_free must be an integer percentage or an integer byte size.
    Valid values: "10%", "1%", "567", "9B", "1023kB", "57Mb", "999GiB" 
    """
    try:
        return parse_percent(target_free), True
    except ValueError:
        pass
    
    m = re.search(r'^(\d+(?:\.\d+)?)([kmg]i?|)b?$', target_free, re.IGNORECASE)
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
            
        return int(val), False
    
    return int(target_free), False


def parse_keep(keep):
    """
    The value of keep must be an integer percentage or a count.
    Example of valid values: "10%", "1%", "567"
    Example of invalid values: "10 %", "1 %", "567", "abc"
    """
    try:
        return parse_percent(keep), True
    except ValueError:
        return int(keep), False


def parse_args():
    parser = OptionParser(usage="Usage: %prog [options] SOURCE TARGET TARGET_FREE")
    parser.add_option("-k", "--keep", dest="keep", metavar="KEEP", default="0",
                      help="minimum number of items currently in TARGET that will be kept")
    parser.add_option("--delete-only-in-target", action="store_true", default=False,
                      help="delete media found in the target that is not in the source. ARE YOU SURE YOU WANT THIS?!")
    (options, args) = parser.parse_args()
    
    if len(args) != 3:
        parser.error("Incorrect number of arguments")
    
    source = args[0]
    target = args[1]
    options.target_free, options.target_free_is_percent = parse_target_free(args[2])
    options.keep, options.keep_is_percent = parse_keep(options.keep)
    return source, target, options


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


def process_media_only_in_target(source_media, target_media, must_delete, target_dir):
    """
    Finds media in the target which are not in the source.
    If the must_delete parameter is True, then the media is deleted_media.
    Remove the media from target_media.
    """
    only_in_target = set(target_media) - set(source_media)
    
    if only_in_target:
        deleted_media = {}
        
        if must_delete:
            print 'Deleting the following items in the target directory that are not in the source directory:'
            def f(path):
                full_path = os.path.join(target_dir, path)
                delete(full_path)
        else:
            print 'The following items in the target directory will be ignored because they are not in the source directory:'
            def f(path):
                pass
        
        for path in sorted(only_in_target, key=str.upper):
            print "\t", path
            f(path)
            move_media(path, target_media, deleted_media)
        
        print


def process_kept_media(target_media, count):
    kept_media = MediaWithSize()
    
    while len(kept_media) < count and len(target_media) > 0:
        chosen = random.choice(target_media.keys())
        move_media(chosen, target_media, kept_media)
    

    if kept_media > 0:
        print 'Keeping %d items out of %d' % (len(kept_media), len(target_media))
    
    return kept_media


def select_media(source_media, kept_media, target_available_size):
    selected_media = MediaWithSize()
    
    while selected_media.size < target_available_size and len(source_media) > 0:
        chosen = random.choice(source_media.keys())
        if chosen in kept_media:
            del source_media[chosen]
        else:
            move_media(chosen, source_media, selected_media)
    
    return selected_media


def delete_media(target_media, kept_media, selected_media, target_dir):
    for item in sorted_media(target_media):
        if item not in selected_media and item not in kept_media:
            print 'Deleting:', item
            item_path = os.path.join(target_dir, item)
            delete(item_path)
        else:
            print 'Keeping:', item


def copy_media(source_media, target_media, kept_media, selected_media, source_dir, target_dir):
    for path in sorted_media(selected_media):
        if path not in target_media and path not in kept_media:
            print 'Copying:', path
            full_source_path = os.path.join(source_dir, path)
            full_target_path = os.path.join(target_dir, path)
            copy(full_source_path, full_target_path)


def main():
    source_dir, target_dir, options = parse_args()
    
    print 'Scanning source: %s...' % source_dir
    source_media = dict((item.path, item) for item in scan_media_dir(source_dir))
    print "%d items found" % len(source_media)
    
    print 'Scanning target: %s...' % target_dir
    target_media = dict((item.path, item) for item in scan_media_dir(target_dir))
    print "%d items found" % len(target_media)
    
    print
    
    
    process_media_only_in_target(source_media, target_media, options.delete_only_in_target, target_dir)
    
    
    if options.keep_is_percent:
        keep_count = len(target_media) * options.keep / 100
    else:
        keep_count = options.keep
    kept_media = process_kept_media(target_media, keep_count)
    
    
    vfsstat = os.statvfs(target_dir)
    if options.target_free_is_percent:
        target_total_size = vfsstat.f_bsize * vfsstat.f_blocks
        target_nouse_size = target_total_size * options.target_free / 100
    else:
        target_nouse_size = options.target_free
    target_free_size = vfsstat.f_bsize * vfsstat.f_bavail
    target_used_size = sum(item.size for item in target_media.itervalues())
    target_available_size = target_used_size + target_free_size - target_nouse_size
    selected_media = select_media(source_media, kept_media, target_available_size)
    
    
    delete_media(target_media, kept_media, selected_media, target_dir)
    
    
    copy_media(source_media, target_media, kept_media, selected_media, source_dir, target_dir)
    
    
    """
    # The space currently used by media 
    current_target_used = sum(item.size for item in target_media.itervalues())
    
    
    vfsstat = os.statvfs(target_dir)
    current_target_free = vfsstat.f_bsize * vfsstat.f_bavail
    
    if options.target_free_is_percent:
        target_total = vfsstat.f_bsize * vfsstat.f_blocks
        target_free_bytes = target_total * options.target_free / 100
    else:
        target_free_bytes = options.target_free
    
    target_space_to_use = current_target_used + current_target_free - target_free_bytes
    
    
    if options.keep_is_percent:
        keep_count = len(target_media) * options.keep / 100
    else:
        keep_count = options.keep
    
    
    selected_source = {}
    selected_source_size = 0
    
    # Forces some items to be selected
    if keep_count > 0:
        print 'Keeping %d items out of %d' % (keep_count, len(target_media))
        target_media2 = dict(**target_media)
        while len(selected_source) < keep_count and len(target_media2) > 0:
            chosen_path = random.choice(target_media2.keys())
            chosen_item = target_media2[chosen_path]
            del target_media2[chosen_path]
            del source_media[chosen_path]
            selected_source[chosen_path] = chosen_item
            selected_source_size += chosen_item.size
    
    
    # Select the source items according to the target space to use
    while len(source_media) > 0:
        chosen_path = random.choice(source_media.keys())
        chosen_item = source_media[chosen_path]
        del source_media[chosen_path]
        
        if selected_source_size + chosen_item.size < target_space_to_use:
            selected_source[chosen_path] = chosen_item
            selected_source_size += chosen_item.size
        
    
    
    # Delete from the target the items that were not selected
    for path in sorted(target_media.keys(), key=str.upper):
        if path in selected_source:
            print 'Keeping:', path
        else:
            full_path = os.path.join(target_dir, path)
            print 'Deleting:', path
            remove(full_path)
            del target_media[path]
    
    print
    
    # Copy!
    for path in sorted(selected_source.iterkeys(), key=str.upper):
        print 'Copying:', path
        full_source_path = os.path.join(source_dir, path)
        full_target_path = os.path.join(target_dir, path)
        if os.path.isdir(full_source_path):
            if os.path.isdir(full_target_path):
                remove(full_target_path)
            shutil.copytree(full_source_path, full_target_path, ignore=ignore_non_media)
        else:
            dir, _ = os.path.split(full_target_path)
            if not os.path.isdir(dir):
                os.makedirs(dir)
            shutil.copy(full_source_path, full_target_path)


def ignore_non_media(dirpath, contents):
    ignored = []
    for item in contents:
        full_path = os.path.join(dirpath, item)
        _, ext = os.path.splitext(item)
        if os.path.isfile(full_path) and not is_media_ext(ext):
            ignored.append(item)
    return ignored
    """


if __name__ == '__main__':
    main()
