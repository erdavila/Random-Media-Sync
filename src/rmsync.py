#!/usr/bin/env python
import random

from rms.media import Media
import rms.debug
import rms.files
import rms.options
import rms.scanner
import rms.text


#rms.debug.ENABLED = True


def process_media_in_dst_only(dst_only, dst_dir, must_delete):
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


def delete_media(dst_delete, dst_dir):
    if dst_delete:
        print "Deleting %s" % rms.text.format_bytesize(dst_delete.size)
        for item in dst_delete.sorted():
            print 'Deleting: %s' % item
            rms.files.delete(dst_dir, item)
        print


def copy_media(src_sel_copy, src_dir, dst_dir):
    if src_sel_copy:
        print "Copying %s" % rms.text.format_bytesize(src_sel_copy.size)
        for num, path in enumerate(src_sel_copy.sorted(), 1):
            print 'Copying (%d/%d): %s' % (num, len(src_sel_copy), path)
            rms.files.copy(src_dir, dst_dir, path)
        print


def mixed_mode(src_sel_copy, dst_delete, src_dir, dst_dir, device_free_target):
    total_items = len(src_sel_copy) + len(dst_delete)
    i = 0
    
    for path in src_sel_copy:
        item = src_sel_copy[path]
        
        while len(dst_delete) > 0 and rms.files.get_device_data(dst_dir).free + item.size < device_free_target:
            path_delete, _ = dst_delete.popitem()
            i += 1
            print 'Deleting (%d/%d): %s' % (i, total_items, path_delete)
            rms.files.delete(dst_dir, path_delete)
        
        i += 1
        print 'Copying  (%d/%d): %s' % (i, total_items, path)
        rms.files.copy(src_dir, dst_dir, path)
    
    # Delete remaining items
    for path_delete in dst_delete:
        i += 1
        print 'Deleting (%d/%d): %s' % (i, total_items, path_delete)
        rms.files.delete(dst_dir, path_delete)
    
    print
    

def main():
    options = rms.options.get_options()
    if rms.debug.ENABLED:
        rms.debug.log('Resulting options:')
        rms.debug.log(src_dir=options.src_dir)
        rms.debug.log(dst_dir=options.dst_dir)
        rms.debug.log(keep=options.keep, keep_is_percent=options.keep_is_percent)
        rms.debug.log(free=options.free, free_type=options.free_type)
        rms.debug.log(ignore=options.ignore)
        rms.debug.log(forced_albums=options.forced_albums)
        rms.debug.log(not_albums=options.not_albums)
        rms.debug.log(dry_run=options.dry_run)
        rms.debug.log(mixed_mode=options.mixed_mode)
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
    
    
    # Finds media in the destination which are not in the source.
    dst_only = dst.partition(src)
    process_media_in_dst_only(dst_only, options.dst_dir, options.delete_in_dst_only)
    
    
    device_data = rms.files.get_device_data(options.dst_dir)
    print "Total size of the destination device: %s" % rms.text.format_bytesize(device_data.total)
    print "Media currently in the destination device: %s (%s)" % (rms.text.format_bytesize(dst.size), rms.text.format_percent(dst.size, device_data.total))
    print "Current free space in the destination device: %s (%s)" % (rms.text.format_bytesize(device_data.free), rms.text.format_percent(device_data.free, device_data.total))
    print
    
    
    if options.keep_is_percent:
        keep_count = len(dst) * options.keep / 100
    else:
        keep_count = options.keep
    
    dst_kept = process_kept_media(src, dst, keep_count)
    
    
    if options.free_type == 'BYTES':
        device_free_target = options.free
    elif options.free_type == 'PERCENT':
        device_free_target = device_data.total * options.free / 100
    else:
        assert options.free_type == 'CURRENT'
        assert options.free is None
        device_free_target = device_data.free
    
    src_selected_size_target = dst.size + device_data.free - device_free_target
    src_selected = select_media(src, src_selected_size_target)
    
    
    dst_delete = dst.partition(src_selected)
    src_sel_copy = src_selected.partition(dst)
    
    if options.mixed_mode:
        mixed_mode(src_sel_copy, dst_delete, options.src_dir, options.dst_dir, device_free_target)
    else:
        delete_media(dst_delete, options.dst_dir)
        copy_media(src_sel_copy, options.src_dir, options.dst_dir)
    
    device_data = rms.files.get_device_data(options.dst_dir)
    dst_media_size = dst.size + dst_kept.size + src_sel_copy.size
    print "Total size of the destination device: %s" % rms.text.format_bytesize(device_data.total)
    print "Media in the destination device: %s (%s)" % (rms.text.format_bytesize(dst_media_size), rms.text.format_percent(dst_media_size, device_data.total))
    print "Free space in the destination device: %s (%s)" % (rms.text.format_bytesize(device_data.free), rms.text.format_percent(device_data.free, device_data.total))


if __name__ == '__main__':
    main()
