import os.path
import shutil
from collections import namedtuple

import rms.scanner as scanner


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
            os.rmdir(dst)
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
        if os.path.isfile(full_path) and not scanner.is_media_file(item):
            ignored.append(item)
    return ignored


DeviceData = namedtuple('DeviceData', 'total,free')

def get_device_data(device_path):
    vfsstat = os.statvfs(device_path)
    total = vfsstat.f_bsize * vfsstat.f_blocks
    free = vfsstat.f_bsize * vfsstat.f_bavail
    return DeviceData(total=total, free=free)
