#!/usr/bin/env python3
"""Pack HakiOS's U-Boot for the Xiaomi 12 (cupid) as an Android boot image for `fastboot boot`.

Same shape as the common repository's tools/mkubootimg.py — gzip(u-boot.bin) followed by the phone's
device tree, which is what ABL expects — with the two values that are measured facts on waipio
instead of redwood's defaults: header version 4, and os_version/os_patch_level left at 0. With
anything else ABL answers OKAY and boots the slot instead (see docs/boot-runbook.md).

  tools/mkuboot-cupid.py --uboot build/u-boot.bin --dtb cupid-u-boot.dtb --out hakios-uboot-cupid.img
"""
import argparse
import gzip
import os
import subprocess
import sys

HEADER = 4               # waipio ABL: v1 is accepted but boots the slot instead
OS_VERSION, OS_PATCH = '0', '0'


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--uboot', required=True, help='u-boot.bin (CONFIG_LINUX_KERNEL_IMAGE_HEADER)')
    ap.add_argument('--dtb', required=True, help='the device tree, from tools/uboot-dts.py through dtc')
    ap.add_argument('--mkbootimg', default='mkbootimg.py')
    ap.add_argument('--out', default='hakios-uboot-cupid.img')
    a = ap.parse_args()

    ub = open(a.uboot, 'rb').read()
    dtb = open(a.dtb, 'rb').read()
    if b'ARM\x64' not in ub[:64]:
        sys.exit('mkuboot-cupid.py: u-boot.bin has no arm64 image header '
                 '(CONFIG_LINUX_KERNEL_IMAGE_HEADER)')
    if dtb[:4] != bytes.fromhex('d00dfeed'):
        sys.exit('mkuboot-cupid.py: the device tree is not a dtb (no d00dfeed)')
    if b'simple-framebuffer' not in dtb:
        sys.exit('mkuboot-cupid.py: the device tree has no simple-framebuffer node, so U-Boot would have\n'
                 '  nothing to write the console on: run tools/uboot-dts.py first')

    kernel = os.path.abspath('u-boot-kernel.bin')
    with open(kernel, 'wb') as f:
        f.write(gzip.compress(ub, 6) + dtb)

    cmd = [sys.executable, a.mkbootimg, '--kernel', kernel, '--header_version', str(HEADER),
           '--os_version', OS_VERSION, '--os_patch_level', OS_PATCH, '-o', a.out]
    print(' '.join(cmd))
    subprocess.check_call(cmd)
    print('%s: %d bytes (u-boot %d gz\'d, dtb %d, header v%d, os_version %s/%s)'
          % (a.out, os.path.getsize(a.out), len(ub), len(dtb), HEADER, OS_VERSION, OS_PATCH))


if __name__ == '__main__':
    main()