import sys
from optparse import OptionParser

import rms.text
import rms.debug


def get_options():
    options = parse_args()
    
    if rms.debug.ENABLED:
        rms.debug.log('Command-line options:')
        rms.debug.log(src_dir=options.src_dir)
        rms.debug.log(dst_dir=options.dst_dir)
        rms.debug.log(keep=options.keep)
        rms.debug.log(free=options.free)
        rms.debug.log(ignore=options.ignore)
        rms.debug.log(forced_albums=options.forced_albums)
        rms.debug.log(not_albums=options.not_albums)
        rms.debug.log(dry_run=options.dry_run)
        rms.debug.log(delete_in_dst_only=options.delete_in_dst_only)
        rms.debug.log()
    
    if options.config_file is not None:
        process_config_file(options)
    
    check_options(options)
    
    return options


def parse_args():
    import re
    def clean(s):
        """Collapse sequence of blank spaces"""
        return re.sub(r'\s+', ' ', s)
    
    
    parser = OptionParser(usage="Usage: %prog [options] [[SOURCE] DESTINATION]")
    
    parser.add_option("-s", "--source", dest="src_dir", default=None, metavar="SOURCE",
                      help="The source media directory.")
    parser.add_option("-d", "--dest", dest="dst_dir", default=None, metavar="DESTINATION",
                      help="The destination media directory.")
    parser.add_option("-f", "--free", dest="free", metavar="FREE", default=None,
                      help=clean("""Minimum amount of space that will be let unused
                          in the destination device. Can be a percentage ("50%",
                          "0%", "25.7%", etc.) or a byte-size value ("1gb", "2.5GiB",
                          "10mB", etc.). Default: the current free space."""))
    parser.add_option("-k", "--keep", dest="keep", metavar="KEEP", default=None,
                      help=clean("""Minimum number of items currently in DESTINATION
                          that will be kept. Can be a percentage (see --free option
                          above) or an absolute number of items. Default: 0."""))
    parser.add_option("--ignore", metavar="ITEM-PATH", action="append", dest="ignore", default=[],
                      help="Ignore an item.")
    parser.add_option("--is-album", metavar="DIR-PATH", action="append", dest="forced_albums", default=[],
                      help="Force a directory item to be treated as an album.")
    parser.add_option("--is-not-album", metavar="DIR-PATH", action="append", dest="not_albums", default=[],
                      help="Force a directory item to not be treated as an album.")
    parser.add_option("-c", "--cfg", dest="config_file", default=None,
                      help="Configuration file.")
    parser.add_option("-n", "--dry-run", action="store_true", default=False,
                      help="Do not delete or copy anything.")
    parser.add_option("--delete-in-dst-only", action="store_true", default=False,
                      help=clean("""Delete media found in the destination which are not
                          in the source. ARE YOU SURE YOU WANT TO DO THIS?!"""))
    
    (options, args) = parser.parse_args()
    
    if args:
        options.dst_dir = args.pop(-1)
    
    if args:
        options.src_dir = args.pop(-1)
    
    if args:
        parser.error("Too many arguments")
    
    return options


def process_config_file(options):
    def single_option(option, arg, options_attr):
        if arg is None:
            sys.exit('Option "%s" in config file requires an argument' % option)
        if getattr(options, options_attr) is None:
            setattr(options, options_attr, arg)
    
    def list_option(option, arg, options_attr):
        if arg is None:
            sys.exit('Option "%s" in config file requires an argument' % option)
        getattr(options, options_attr).append(arg)
    
    def bool_option(option, arg, options_attr):
        if arg is not None:
            sys.exit('Option "%s" in config file does not requires an argument' % option)
        setattr(options, options_attr, True)
    
    
    filename = options.config_file
    
    rms.debug.log('Config file options:')
    with open(filename) as f:
        for line in f:
            if line.startswith('#'):
                # A comment
                continue
            
            line = line.strip()
            if line == '':
                continue
            
            try:
                i = line.index(' ')
            except ValueError:
                option = line
                arg = None
            else:
                # An option with argument
                option = line[:i].strip()
                arg = line[i+1:].strip()
            
            rms.debug.log(**{option:arg})
            if option == 'source':
                single_option(option, arg, 'src_dir')
            elif option == 'dest':
                single_option(option, arg, 'dst_dir')
            elif option in ('free', 'keep'):
                single_option(option, arg, option)
            elif option == 'ignore':
                list_option(option, arg, 'ignore')
            elif option == 'is-album':
                list_option(option, arg, 'forced_albums')
            elif option == 'is-not-album':
                list_option(option, arg, 'not_albums')
            elif option == 'dry-run':
                bool_option(option, arg, 'dry_run')
            elif option == 'delete-in-dst-only':
                bool_option(option, arg, 'delete_in_dst_only')
            else:
                sys.exit('"%s" is not a valid config file option' % option)
    rms.debug.log()


def check_options(options):
    if options.dst_dir is None:
        sys.exit("DESTINATION not specified")
    
    if options.src_dir is None:
        sys.exit("SOURCE not specified")
    
    
    if options.free is None:
        options.free_type = 'CURRENT'
    else:
        try:
            options.free = rms.text.parse_percent(options.free)
            options.free_type = 'PERCENT'
        except ValueError:
            options.free = rms.text.parse_bytesize(options.free)
            options.free_type = 'BYTES'
    
    if options.keep is None:
        options.keep = 0
        options.keep_is_percent = False
    else:
        try:
            options.keep = rms.text.parse_percent(options.keep)
            options.keep_is_percent = True
        except ValueError:
            options.keep = int(options.keep)
            options.keep_is_percent = False
    
    if options.dry_run:
        rms.files.delete = rms.files.copy = lambda *args:None
