#!/bin/bash
# boot-cupid.sh — drive the XNU loader over fastboot on Windows/git-bash.
#
# xl (in the common repo) is a Linux script that uses flock, which Git for Windows does not ship.
# This does the same three operations with plain fastboot and the upstream payload tools:
#
#   enter      build usb-payload.bin + xnu-usb.img, then fastboot boot it (temporary, no flash)
#   selftest   stage a kernel-only payload and ask the resident loader to run its self test
#   run        stage kernel + ramdisk and run it
#   log        fetch the loader log to logs/loader.log
#   state      show adb/fastboot state
#
# No partition is written. A reboot returns the phone to Android.

set -euo pipefail

COMMON=${COMMON:-C:/Users/heri/hakios/hakios-xnu-kernel}
PT=${PT:-C:/Users/heri/Downloads/platform-tools}
K=${K:-hakios-kernel}
L=${L:-xnuloader/loader.efi}
RD=${XL_RAMDISK:-userland/hello}
SECS=${XL_SECS:-8}

export PATH="$PATH:$PT"
cd "$COMMON"

need() { command -v "$1" >/dev/null || { echo "boot-cupid: $1 not found (set PT=...)" >&2; exit 1; }; }
need fastboot
need python3

state() {
  if fastboot devices 2>/dev/null | grep -q fastboot; then
    if [ "$(fastboot getvar product 2>&1 | grep '^product:')" = "product: xnuloader" ]; then
      echo loader
    else
      echo fastboot
    fi
  elif adb get-state 2>/dev/null | grep -q device; then
    echo android
  else
    echo absent
  fi
}

enter() {
  [ -f "$L" ] || { echo "boot-cupid: no loader at $L" >&2; exit 1; }
  [ "$(state)" = loader ] && { echo "boot-cupid: loader already up"; return 0; }
  if [ "$(state)" = android ]; then
    adb reboot bootloader
    for _ in $(seq 1 20); do
      [ "$(state)" != absent ] && break
      sleep 3
    done
  fi
  [ "$(state)" = fastboot ] || { echo "boot-cupid: phone not in fastboot" >&2; exit 1; }
  python3 xnuloader/mkpayload.py -o usb-payload.bin "loader.efi=$L" --usb >/dev/null
  python3 mkxnuimg.py -p usb-payload.bin -o xnu-usb.img >/dev/null
  local ok=
  for _ in 1 2; do
    fastboot boot xnu-usb.img 2>&1 | grep -q OKAY || { sleep 3; continue; }
    sleep 6
    [ "$(state)" = loader ] && { ok=1; break; }
  done
  [ -n "$ok" ] || { echo "boot-cupid: loader did not come up (bootloader locked?)" >&2; exit 1; }
  echo "boot-cupid: loader is up"
  fastboot getvar product 2>&1 | grep '^product:'
}

stage_payload() {
  [ -f "$K" ] || { echo "boot-cupid: no kernel at $K" >&2; exit 1; }
  local cmd="loader_return_after=${SECS} epoch=$(date +%s) sb_delay=8 -v"
  if [ "${1:-}" = selftest ]; then
    python3 xnuloader/mkpayload.py -o run-payload.bin "kernel=$K" --cmdline "$cmd" >/dev/null
  else
    [ -f "$RD" ] || { echo "boot-cupid: ramdisk $RD not found (set XL_RAMDISK=...)" >&2; exit 1; }
    python3 xnuloader/mkpayload.py -o run-payload.bin "kernel=$K" "ramdisk=$RD" --cmdline "$cmd" >/dev/null
  fi
  fastboot stage run-payload.bin 2>&1 | grep -q OKAY || { echo "boot-cupid: upload failed" >&2; exit 1; }
  echo "boot-cupid: payload staged"
}

log() {
  mkdir -p logs
  fastboot oem log 2>&1 | tee logs/loader.log
}

case "${1:-state}" in
  enter) enter ;;
  selftest) enter; stage_payload selftest; fastboot oem selftest 2>&1; sleep "$SECS"; log ;;
  run) enter; stage_payload run; fastboot oem run 2>&1; sleep "$SECS"; log ;;
  log) log ;;
  state) state ;;
  *) echo "usage: $0 {enter|selftest|run|log|state}" >&2; exit 2 ;;
esac
