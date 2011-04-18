#!/usr/bin/env python
import os
import random

from rms.media import Media
import rms.debug
import rms.files
import rms.options
import rms.scanner
import rms.text


#rms.debug.ENABLED = True


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
        for item in dst_delete.sorted():
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
    options = rms.options.get_options()
    if rms.debug.ENABLED:
        rms.debug.log('Final options:')
        rms.debug.log(src_dir=options.src_dir)
        rms.debug.log(dst_dir=options.dst_dir)
        rms.debug.log(keep=options.keep, keep_is_percent=options.keep_is_percent)
        rms.debug.log(free=options.free, free_type=options.free_type)
        rms.debug.log(ignore=options.ignore)
        rms.debug.log(forced_albums=options.forced_albums)
        rms.debug.log(not_albums=options.not_albums)
        rms.debug.log(dry_run=options.dry_run)
        rms.debug.log(delete_in_dst_only=options.delete_in_dst_only)
        rms.debug.log()
    
    scanner = rms.scanner.Scanner(options.ignore, options.forced_albums, options.not_albums)
    
    print 'Scanning source: %s' % options.src_dir
    src = scanner.scan(options.src_dir)
    print "%d items found in %s" % (len(src), rms.text.format_bytesize(src.size))
    
    print
    
    print 'Scanning destination: %s' % options.dst_dir
    dst = scanner.scan(options.dst_dir)
    print "%d items found in %s" % (len(dst), rms.text.format_bytesize(dst.size))
    
    print
    
    
    process_media_in_dst_only(src, dst, options.dst_dir, options.delete_in_dst_only)
    
    
    vfsstat = os.statvfs(options.dst_dir)
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
    
    
    delete_media(src_selected, dst, options.dst_dir)
    
    
    src_sel_copy = copy_media(src_selected, dst, options.src_dir, options.dst_dir)
    

    vfsstat = os.statvfs(options.dst_dir)
    device_total = vfsstat.f_bsize * vfsstat.f_blocks
    device_free_current = vfsstat.f_bsize * vfsstat.f_bavail
    dst_media_size = dst.size + dst_kept.size + src_sel_copy.size
    print "Total size of the destination device: %s" % rms.text.format_bytesize(device_total)
    print "Media in the destination device: %s (%s)" % (rms.text.format_bytesize(dst_media_size), rms.text.format_percent(dst_media_size, device_total))
    print "Free space in the destination device: %s (%s)" % (rms.text.format_bytesize(device_free_current), rms.text.format_percent(device_free_current, device_total))


if __name__ == '__main__':
    main()
