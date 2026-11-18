# Cupid boot runbook — first boot

This is the runbook for the first HakiOS boot on the Xiaomi 12. Every command below is
**temporary**: `fastboot boot` streams an image into RAM; nothing is flashed, no partition is
written, and Android stays intact. A reboot returns the phone to Android.

## 1. Artifacts

Built by CI, not fabricated:

| Artifact | CI run | SHA256 |
|---|---|---|
| `SILICIUM_UEFI.fd` | `44197867816` | see run summary |
| `cupid-kernel` | `44213175444` | `914c5fe1ef04d1f1d2e1709a417690824edd8ee81341bf147ad28a150b16d70d` |
| `cupid-loader.efi` | `44213175444` | `827c444d73e7daaab486427c79159facaa0ca3d1f0a2f426392eb2ed07bd8bce` |

The loader was built with `xnuloader/mkidentity.sh --placeholder`: **no Apple identity, no
IPSW**. It can boot the open kernel with an Apple-free ramdisk. It cannot start stock Darwin.
A full iOS user-space boot needs an IPSW 16.5 supplied by the user.

## 2. Put artifacts where `xl` expects them

`xl` runs from the **common** repository (`C:\Users\heri\hakios\hakios-xnu-kernel`):

```bash
cd C:/Users/heri/hakios/hakios-xnu-kernel
cp <artifacts>/cupid-kernel      hakios-kernel
cp <artifacts>/cupid-loader.efi  xnuloader/loader.efi
```

Verify:

```bash
sha256sum hakios-kernel xnuloader/loader.efi
file hakios-kernel    # Mach-O 64-bit arm64 executable
```

## 3. Host tools (Windows / git-bash)

`platform-tools` is not on `PATH` by default. Add it:

```bash
export PATH="$PATH:/c/Users/heri/Downloads/platform-tools"
adb version
fastboot version
```

The phone must be authorized for ADB at least once, or already in fastboot.

## 4. Connect the phone

Cable, then confirm:

```bash
adb devices -l          # expect: cupid 2201123G ... device
fastboot devices        # expect: <serial> fastboot
```

If the phone is in Android, `xl enter` reboots it into fastboot itself.

## 5. Get into the resident loader

```bash
cd C:/Users/heri/hakios/hakios-xnu-kernel
./xl enter
```

`xl enter` builds `usb-payload.bin` from `loader.efi`, wraps it into `xnu-usb.img`, then does
`fastboot boot xnu-usb.img` (twice if needed). Success looks like:

```
xl: loader is up
```

Confirm independently:

```bash
fastboot getvar product    # expect: product: xnuloader
```

`xl enter` is itself the definitive unlock check: a locked bootloader rejects the boot.

## 6. First kernel run — no IPSW

The smallest test exercises the kernel -> loader return path, with no ramdisk:

```bash
./xl selftest
./xl log                   # fetch logs/loader.log from the phone
```

Then a normal run (the default ramdisk is `userland/root.apfs`; set `XL_RAMDISK=userland/hello`
for the tiny raw-syscall program, which boots through mockfs):

```bash
XL_RAMDISK=userland/hello ./xl run
./xl screenshot logs/cupid-first-boot.png
./xl log
```

A framebuffer screenshot is the actual evidence of a boot — a green CI build is not.

## 7. First boot attempt — evidence and result (not yet a boot)

The first attempt on the real phone (serial `341db2b`) did **not** reach the loader. Evidence:

- `fastboot oem device-info` → `Device unlocked: true`, `critical unlocked: true`. Unlock is not the blocker.
- `fastboot boot <image>` → `OKAY` on every attempt; the image is transferred and accepted.
- Vendor UEFI log (`/dev/block/by-name/logfs`, FAT12, `UefiLog1.txt`): `Handling Cmd: download:001dd000`,
  `Handling Cmd: boot`, `Decompressing kernel image total time: 222 ms`, then `Start EBS`. ABL accepted
  and decompressed our kernel and handed off; no loader banner followed. The later `Cmdline:` and
  `initrd size` lines come from `vendor_boot`, not from the boot image.
- Screen stayed black; the phone returned to fastboot only after the key combo.
- The BootShim taken from the CI image carried `FD_BASE=0xA2F00000`. It was changed to `0xA7000000`,
  the PT_LOAD address measured from the phone's own `uefi_a.img`, and the FD was rebuilt in
  [run 44253508613](https://github.com/hrihq/hakios-device-cupid/actions/runs/44253508613). The result
  was unchanged: no display, no loader.

So the failure is inside BootShim / the linked FD, not in transfer, unlock or verification. The FD
links and the platform compiles; neither is a boot test. A serial log is needed to go further.

## 8. Safety

- `fastboot boot` only. **Never** `fastboot flash`.
- No partition is touched. Do not run `xl ramdisk` against a partition; it is a RAM upload.
- Do not change persistent boot configuration (`fastboot set_active`, `flash`, `erase`).
- If anything hangs: `./xl hang` waits for the watchdog and returns to Android; `./xl reboot`
  leaves the loader. Physical power hold is the last resort.
- Disconnecting the cable after the artifacts have been downloaded is safe.

## 8. What is NOT yet validated

- GPU acceleration, display driver, touch, audio, Wi-Fi/BT, camera, battery.
- First boot is expected to use the UEFI framebuffer plus software rendering, like `renoir`.
- `cupid.config` has all phone drivers off. Runtime driver work comes after the first boot.

## 9. U-Boot path (no UART needed)

The site's U-Boot guide (docs/u-boot.md in the common repository) is an alternative boot chain:
ABL fastboot-boots HakiOS's U-Boot, and U-Boot starts the loader from RAM. U-Boot writes its
log to the phone screen and answers `fastboot oem console`, so no serial cable is needed.

- Branch `uboot-cupid` builds it in CI: `.github/workflows/build-uboot.yml`.
- Run 44264429537 is green; artifact `cupid-uboot` holds `hakios-u-boot.img` and `u-boot.bin`.
- The phone's own `uefi/files/Resources/DTBs/cupid.dtb` is converted to a DTS with dtc and used
  as U-Boot's default tree. `CONFIG_SYS_INIT_SP_BSS_OFFSET=0x600000` is required: the default
  1.5 MiB fails `init_sp_bss_offset_check` with this ~780 KiB tree.
- A built image is still not a boot test. Try it with `fastboot boot` only; never flash.
