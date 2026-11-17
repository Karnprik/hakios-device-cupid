# The vendor DXE drivers in this phone's own UEFI

`uefi_a.img`, pulled from `/dev/block/by-name/uefi_a` of the Xiaomi 12 (the ELF64 5 MB partition),
is not a flat firmware volume. It holds one FV at `0x1010`; that FV names two `FV_IMAGE` files whose
payloads are gzip-compressed GUID_DEFINED sections, and each of those decompresses into a nested FV
holding the vendor's own DXE drivers.

`tools/uefi-fv-unpack.py` now follows that chain: gzip by its GUID
`1D301FE9-BE79-4353-91C2-D23BC959AE0C`, then writes the sections it finds (the earlier version wrote
only `index.txt`, and mis-read `DataOffset` by the four bytes of the common section header).

## What is actually in the phone

The two nested FVs (3.9 MB and 2.9 MB decompressed) yield **81 named modules**. Among the ones the
port needs:

| Vendor module in this phone | Platform name |
|---|---|
| `ChipInfo` | `ChipInfoDxe` |
| `HALIOMMU` | `HALIOMMUDxe` |
| `I2C` | `I2CDxe` |
| `SPI` | `SPIDxe` |
| `ClockDxe`, `SdccDxe`, `GpiDxe`, `ICBDxe`, `PmicDxe`, `RngDxe`, `UCDxe`, `VcsDxe` | the same |
| `ScmDxeLA`, `TzDxeLA`, `FeatureEnablerDxe`, `XhciDxe`, `UsbConfigDxe` | the same |

The FVs also hold the **panel configuration for this phone**: `Panel_r66451_120hz_fhd_plus_dsc_cmd*`,
`Panel_boe_*`, `Panel_sharp_*`, and the secondary-panel variants. That is the evidence behind
`docs/panel-facts.txt`: the fitted panel is a Visionox R66451 at 120 Hz.

And the usual EDK2 core: `DxeCore`, `ArmCpuDxe`, `DiskIoDxe`, `PartitionDxe`, `Fat`,
`GraphicsConsoleDxe`, `ConPlatformDxe`, `ConSplitterDxe`, `UsbBusDxe`, `UsbKbDxe`, plus
`QcomChargerApp`, `VibratorDxe` and `SecRSADxe`.

## What this says about the platform's 51 names

`Include/DXE.inc` names 51 `Binaries/cupid/...inf` drivers, inherited from the negroni reference
board (the same SM8450 but a different build). Comparing those 51 with the phone's inventory:

* **16 match** — 12 by the same name, 4 after allowing the `Dxe`/`La` suffix
  (`ChipInfo`→`ChipInfoDxe`, `HALIOMMU`→`HALIOMMUDxe`, `I2C`→`I2CDxe`, `SPI`→`SPIDxe`);
* **35 do not appear** in the two nested FVs: `ButtonsDxe`, `CPRDxe`, `ChargerExDxe`, `CmdDbDxe`,
  `DALSYSDxe`, `DDRInfoDxe`, `DisplayDxe`, `EnvDxe`, `GLinkDxe`, `HWIODxe`, `IPCCDxe`, `LimitsDxe`,
  `NpaDxe`, `PILDxe`, `PILProxyDxe`, `PlatformInfoDxe`, `PmicDxeLa`, `PmicGlinkDxe`,
  `ProjectInfoDxe`, `PwrUtilsDxe`, `QcomChargerDxeLA`, `RpmhDxe`, `SPMIDxe`, `ShmBridgeDxeLA`,
  `SmemDxe`, `TLMMDxe`, `TsensDxe`, `UFSDxe`, `ULogDxe`, `UsbDeviceDxe`, `UsbInitDxe`,
  `UsbMsdDxe`, `UsbPwrCtrlDxe`, `UsbfnDwc3Dxe`, `XhciPciEmulationDxe`.

That is not proof those drivers are absent from the phone: they may be in another FV section the
unpacker still cannot walk (it reports sections at several offsets claiming sizes that do not fit).
It **is** proof that a platform list copied from another board cannot be assumed to match this
phone's firmware -- the reason the porting rules say never to copy another device's configuration
blindly.

## What is still needed

1. Make the unpacker walk the remaining nested sections, or confirm they hold nothing relevant;
2. map the phone's real module GUIDs to the platform's driver list, then replace the inherited names
   with the ones this phone actually provides;
3. only then attempt the FD link. A successful link is still not a boot.

## The phone's own device tree, checked

`prebuilt/device-tree.dtb` was pulled from `/sys/firmware/fdt` through root and staged with `adb pull`
(`adb shell cat` corrupts it with CRLF on Windows). It is a valid FDT: 773,375 bytes, 4,405 nodes
against the platform's stand-in 4,392.

All **44 GPU facts** and the panel identity (Visionox R66451, 120 Hz, 1080x2340) check out against
the phone's own tree. Three differences from the stand-in:

| Fact | Stand-in DTB | The phone's own DTB |
|---|---|---|
| `/soc/xiaomi_touch` | present | not present |
| Synaptics TCM status | `ok` | `disabled` |
| the primary panel's phandle | 1738 | 1778 |

The facts kept in `docs/device-facts.txt` and `docs/panel-facts.txt` are checked in CI against the
committed stand-in, because the phone's own DTB is deliberately not committed. The differences above
are recorded here so they are not mistaken for validation on the phone.
