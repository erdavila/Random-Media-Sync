#!/usr/bin/env python
import os
import random
from optparse import OptionParser

from rms.media import Media
import rms.scanner
import rms.text
import rms.files


def parse_args():
    import re
    def clean(s):
        return re.sub(r'\s+', ' ', s)
    
    
    parser = OptionParser(usage="Usage: %prog [options] SOURCE DESTINATION")
    parser.add_option("-f", "--free", dest="free", metavar="FREE", default=None,
                      help=clean("""Minimum amount of space that will be let unused
                          in the destination device. Can be a percentage ("50%",
                          "0%", "25.7%", etc.) or a byte-size value ("1gb", "2.5GiB",
                          "10mB", etc.). Default: the current free space."""))
    parser.add_option("-k", "--keep", dest="keep", metavar="KEEP", default="0",
                      help=clean("""Minimum number of items currently in DESTINATION
                          that will be kept. Can be a percentage (see TARGET_FREE
                          argument above) or an absolute number of items. Default: 0."""))
    parser.add_option("--ignore", metavar="ITEM-PATH", action="append", dest="ignore", default=[],
                      help="Ignore an item.")
    parser.add_option("--is-album", metavar="DIR-PATH", action="append", dest="forced_albums", default=[],
                      help="Force a directory item to be treated as an album.")
    parser.add_option("--is-not-album", metavar="DIR-PATH", action="append", dest="not_albums", default=[],
                      help="Force a directory item to not be treated as an album.")
    parser.add_option("-n", "--dry-run", action="store_true", default=False,
                      help="Do not delete or copy anything.")
    parser.add_option("--delete-in-dst-only", action="store_true", default=False,
                      help=clean("""Delete media found in the destination which are not
                          in the source. ARE YOU SURE YOU WANT TO DO THIS?!"""))
    (options, args) = parser.parse_args()
    
    if len(args) != 2:
        parser.error("Incorrect number of arguments")
    
    src_dir = args[0]
    dst_dir = args[1]
    
    if options.free is None:
        options.free_type = 'CURRENT'
    else:
        try:
            options.free = rms.text.parse_percent(options.free)
            options.free_type = 'PERCENT'
        except ValueError:
            options.free = rms.text.parse_bytesize(options.free)
            options.free_type = 'BYTES'
    
    try:
        options.keep = rms.text.parse_percent(options.keep)
        options.keep_is_percent = True
    except ValueError:
        options.keep = int(options.keep)
        options.keep_is_percent = False
    
    if options.dry_run:
        def _do_nothing(*args): pass
        rms.files.delete = rms.files.copy = _do_nothing
    
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
                rms.files.delete(dst_dir, path)
        else:
            print 'The following items in the destination directory will be ignored because they are not in the source directory:'
            def f(path):
                pass
        
        for path in dst_only.sorted():
            print "\t", path
            f(path)
        print "\tTotal: %s" % rms.text.format_bytesize(dst_only.size)
        
        print
    
    return dst_only


def process_kept_media(src, dst, keep_count):
    src_kept = Media()
    dst_kept = Media()
    
    while len(dst_kept) < keep_count and len(dst) > 0:
        chosen = random.choice(dst.keys())
        src.move(chosen, src_kept)
        dst.move(chosen, dst_kept)
    
    return dst_kept


def select_media(src, src_selected_size_target):
    src_selected = Media()
    src_not_selected = Media()
    
    while len(src) > 0:
        chosen = random.choice(src.keys())
        
        if src_selected.size + src[chosen].size <= src_selected_size_target:
            src.move(chosen, src_selected)
        else:
            src.move(chosen, src_not_selected)
    
    return src_selected


def delete_media(src_selected, dst, dst_dir):
    dst_delete = dst.partition(src_selected)
    
    if dst_delete:
        print "Deleting %s" % rms.text.format_bytesize(dst_delete.size)
        for num, item in enumerate(dst_delete.sorted(), 1):
            print 'Deleting: %s' % item
            rms.files.delete(dst_dir, item)
        print


def copy_media(src_selected, dst, src_dir, dst_dir):
    src_sel_copy = src_selected.partition(dst)
    
    if src_sel_copy:
        print "Copying %s" % rms.text.format_bytesize(src_sel_copy.size)
        for num, path  in enumerate(src_sel_copy.sorted(), 1):
            print 'Copying (%d/%d): %s' % (num, len(src_sel_copy), path)
            rms.files.copy(src_dir, dst_dir, path)
        print
    
    return src_sel_copy


def main():
    src_dir, dst_dir, options = parse_args()
    
    scanner = rms.scanner.Scanner(options.ignore, options.forced_albums, options.not_albums)
    
    print 'Scanning source: %s' % src_dir
    src = scanner.scan(src_dir)
    print "%d items found in %s" % (len(src), rms.text.format_bytesize(src.size))
    
    print
    
    print 'Scanning destination: %s' % dst_dir
    dst = scanner.scan(dst_dir)
    print "%d items found in %s" % (len(dst), rms.text.format_bytesize(dst.size))
    
    print
    
    
    process_media_in_dst_only(src, dst, dst_dir, options.delete_in_dst_only)
    
    
    vfsstat = os.statvfs(dst_dir)
    device_total = vfsstat.f_bsize * vfsstat.f_blocks
    device_free_current = vfsstat.f_bsize * vfsstat.f_bavail
    print "Total size of the destination device: %s" % rms.text.format_bytesize(device_total)
    print "Media currently in the destination device: %s (%s)" % (rms.text.format_bytesize(dst.size), rms.text.format_percent(dst.size, device_total))
    print "Current free space in the destination device: %s (%s)" % (rms.text.format_bytesize(device_free_current), rms.text.format_percent(device_free_current, device_total))
    print
    
    
    if options.keep_is_percent:
        keep_count = len(dst) * options.keep / 100
    else:
        keep_count = options.keep
    
    dst_kept = process_kept_media(src, dst, keep_count)
    
    
    if options.free_type == 'BYTES':
        device_free_target = options.free
    elif options.free_type == 'PERCENT':
        device_free_target = device_total * options.free / 100
    else:
        assert options.free_type == 'CURRENT'
        assert options.free is None
        device_free_target = device_free_current
    
    src_selected_size_target = dst.size + device_free_current - device_free_target
    src_selected = select_media(src, src_selected_size_target)
    
    
    delete_media(src_selected, dst, dst_dir)
    
    
    src_sel_copy = copy_media(src_selected, dst, src_dir, dst_dir)
    

    vfsstat = os.statvfs(dst_dir)
    device_total = vfsstat.f_bsize * vfsstat.f_blocks
    device_free_current = vfsstat.f_bsize * vfsstat.f_bavail
    dst_media_size = dst.size + dst_kept.size + src_sel_copy.size
    print "Total size of the destination device: %s" % rms.text.format_bytesize(device_total)
    print "Media in the destination device: %s (%s)" % (rms.text.format_bytesize(dst_media_size), rms.text.format_percent(dst_media_size, device_total))
    print "Free space in the destination device: %s (%s)" % (rms.text.format_bytesize(device_free_current), rms.text.format_percent(device_free_current, device_total))


if __name__ == '__main__':
    main()
