#!/usr/bin/env python
import sys
import os
import re
import random
import shutil
from optparse import OptionParser
import rms.scanner as scanner
import rms.text as text
from rms.media import Media


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
        if os.path.isfile(full_path) and not scanner.is_media_ext(ext):
            ignored.append(item)
    return ignored


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
    target_free = args[2]
    
    try:
        options.device_free_target = text.parse_percent(target_free)
        options.device_free_target_is_percent = True
    except ValueError:
        options.device_free_target = text.parse_bytesize(target_free)
        options.device_free_target_is_percent = False
    
    try:
        options.keep = text.parse_percent(options.keep)
        options.keep_is_percent = True
    except ValueError:
        options.keep = int(options.keep)
        options.keep_is_percent = False
    
    if options.dry_run:
        global delete, copy
        def _do_nothing(*args): pass
        delete = copy = _do_nothing
    
    return src_dir, dst_dir, options


def process_media_in_dst_only(src, dst, dst_dir, must_delete):
    """
    Finds media in the destination which are not in the source.
    If the must_delete parameter is True, then the media is deleted.
    Remove the media from dst.
    """
    dst_only = dst.partition(src)
    if dst_only:
        if must_delete:
            print 'Deleting the following items in the destination directory that are not in the source directory:'
            def f(path):
                delete(dst_dir, path)
        else:
            print 'The following items in the destination directory will be ignored because they are not in the source directory:'
            def f(path):
                pass
        
        for path in dst_only.sorted():
            print "\t", path
            f(path)
        print "\tTotal: %s" % text.format_bytesize(dst_only.size)
        
        print
    
    return dst_only


def process_kept_media(src, dst, keep_count):
    src_kept = {}
    dst_kept = Media()
    
    while len(dst_kept) < keep_count and len(dst) > 0:
        chosen = random.choice(dst.keys())
        src.move(chosen, src_kept)
        dst.move(chosen, dst_kept)
    
    return dst_kept


def select_media(src, src_selected_size_target):
    src_selected = Media()
    
    while src_selected.size < src_selected_size_target and len(src) > 0:
        chosen = random.choice(src.keys())
        src.move(chosen, src_selected)
    
    return src_selected


def delete_media(src_selected, dst, dst_dir):
    dst_delete = dst.partition(src_selected)
    
    if dst_delete:
        print "Deleting %s" % text.format_bytesize(dst_delete.size)
        for num, item in enumerate(dst_delete.sorted(), 1):
            print 'Deleting: %s' % item
            delete(dst_dir, item)
        print


def copy_media(src_selected, dst, src_dir, dst_dir):
    src_sel_copy = src_selected.partition(dst)
    
    if src_sel_copy:
        print "Copying %s" % text.format_bytesize(src_sel_copy.size)
        for num, path  in enumerate(src_sel_copy.sorted(), 1):
            print 'Copying (%d/%d): %s' % (num, len(src_sel_copy), path)
            copy(src_dir, dst_dir, path)
        print
    
    return src_sel_copy


def main():
    src_dir, dst_dir, options = parse_args()
    
    print 'Scanning source: %s' % src_dir
    src = Media((item.path, item) for item in scanner.scan_media_dir(src_dir))
    print "%d items found in %s" % (len(src), text.format_bytesize(src.size))
    
    print
    
    print 'Scanning destination: %s' % dst_dir
    dst = Media((item.path, item) for item in scanner.scan_media_dir(dst_dir))
    print "%d items found in %s" % (len(dst), text.format_bytesize(dst.size))
    
    print
    
    
    process_media_in_dst_only(src, dst, dst_dir, options.delete_only_in_dst)
    
    
    vfsstat = os.statvfs(dst_dir)
    device_total = vfsstat.f_bsize * vfsstat.f_blocks
    device_free_current = vfsstat.f_bsize * vfsstat.f_bavail
    print "Total size of the destination device: %s" % text.format_bytesize(device_total)
    print "Media currently in the destination device: %s (%s)" % (text.format_bytesize(dst.size), text.format_percent(dst.size, device_total))
    print "Current free space in the destination device: %s (%s)" % (text.format_bytesize(device_free_current), text.format_percent(device_free_current, device_total))
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
    print "Total size of the destination device: %s" % text.format_bytesize(device_total)
    print "Media in the destination device: %s (%s)" % (text.format_bytesize(dst_media_size), text.format_percent(dst_media_size, device_total))
    print "Free space in the destination device: %s (%s)" % (text.format_bytesize(device_free_current), text.format_percent(device_free_current, device_total))


if __name__ == '__main__':
    main()
