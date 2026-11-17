#!/bin/bash
# pull-firmware.sh, through root. Some ROMs mount /vendor/firmware_mnt for the system user only, so the
# plain `adb pull` of pull-firmware.sh gets nothing ("not on the phone" for every file) although every
# file is there. This does the same pull by way of su: the firmware is copied, under root, to a
# world-readable staging directory in /data/local/tmp, pulled from there, and the staging directory is
# removed again. Nothing on the phone is changed.
#
# Needs the phone in Android with adb and a root that answers `su -c` (Magisk, KernelSU).
set -e
cd "$(dirname "$0")"   # this is a standalone device repository, not devices/<name> in the common tree
S=/data/local/tmp/cupid-fw

adb get-state >/dev/null

# the copy itself, under root. The firmware names are the phone's own; the globs take what is there.
# The paths are written out in full: adb -> su -> sh is three levels of quoting, and a $S held in a
# variable here would be expanded by the wrong shell.
adb shell "su -c 'mkdir -p $S/gpu $S/wifi $S/audio $S/modem $S/haptic $S/camera'"
adb shell "su -c 'cp /vendor/firmware/gmu_gen70000.bin /vendor/firmware/a730_sqe.fw /vendor/firmware/a730_zap.* $S/gpu/ 2>/dev/null || true'"
adb shell "su -c 'cp /vendor/firmware_mnt/image/qca6490/* /vendor/firmware_mnt/image/bdwlan.* /vendor/firmware/wlan/qca_cld/qca6490/* $S/wifi/ 2>/dev/null || true'"
adb shell "su -c 'cp /vendor/firmware_mnt/image/adsp* $S/audio/ 2>/dev/null || true'"
adb shell "su -c 'cp /vendor/firmware_mnt/image/modem* $S/modem/ 2>/dev/null || true'"
adb shell "su -c 'cp /vendor/firmware/aw8697_haptic.bin $S/haptic/ 2>/dev/null || true'"
adb shell "su -c 'cp /vendor/lib64/camera/com.qti.sensormodule.*.bin $S/camera/ 2>/dev/null || true'"
adb shell "su -c 'chmod -R a+rX $S'"

# the UEFI firmware volume, which holds the vendor DXE drivers. dd off the block devices, read-only,
# into the same staging directory. This phone has a dedicated uefi_a (ELF64, the FV) as well as
# xbl_a (ELF32, the loader); take both, since the drivers may live in either.
for part in uefi_a xbl_a; do
	out="$part.img"
	adb shell "su -c 'dd if=/dev/block/by-name/$part of=$S/$out bs=4096 status=none'" >/dev/null 2>&1 \
		|| echo "pull-firmware-root.sh: $part: not readable"
done

rm -rf fw-stage
adb pull "$S" fw-stage >/dev/null
adb shell "su -c 'rm -rf $S'" >/dev/null 2>&1 || true

rm -rf fw-gpu fw-wifi fw-audio fw-modem fw-haptic fw-camera
for d in gpu wifi audio modem haptic camera; do
	[ -d "fw-stage/$d" ] && mv "fw-stage/$d" "fw-$d"
done
for img in uefi_a.img xbl_a.img; do
	if [ -s "fw-stage/$img" ]; then
		mv "fw-stage/$img" "$img"
		echo "pull-firmware-root.sh: $img: $(wc -c < "$img" | tr -d ' ') bytes"
	else
		echo "pull-firmware-root.sh: $img: not found"
	fi
done
rm -rf fw-stage

for d in fw-gpu fw-wifi fw-audio fw-modem fw-haptic fw-camera; do
	echo "pull-firmware-root.sh: $d: $(ls -1 "$d" 2>/dev/null | wc -l | tr -d ' ') files"
done

# the phone's own device tree, which only root can read. Stage it and adb pull: `adb shell cat`
# converts LF to CRLF on Windows and corrupts the binary.
mkdir -p prebuilt
adb shell 'su -c "cp /sys/firmware/fdt /data/local/tmp/cupid-fdt && chmod a+r /data/local/tmp/cupid-fdt"' >/dev/null 2>&1 \
	&& adb pull /data/local/tmp/cupid-fdt prebuilt/device-tree.dtb >/dev/null 2>&1 \
	&& [ -s prebuilt/device-tree.dtb ] \
	|| echo "pull-firmware-root.sh: /sys/firmware/fdt: not readable; the platform's own DTB stays"
adb shell 'su -c "rm -f /data/local/tmp/cupid-fdt"' >/dev/null 2>&1 || true

echo "pull-firmware-root.sh: done; the staging directory is removed"
