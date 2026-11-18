# Cupid boot-path readiness audit

Target: Xiaomi 12 (cupid), Qualcomm SM8450 / Snapdragon 8 Gen 1.

This document separates firmware components that are referenced by the platform
from components that are present as source, linked into the image, and verified
on physical hardware. A driver name in a DSC/APRIORI list is not proof that the
driver binary exists or that the device initialized successfully.

## Current repository evidence

| Area | Repository evidence | What can be concluded |
|---|---|---|
| USB device / Fastboot transport | `Include/DXE.inc` and `Include/APRIORI.inc` reference Qualcomm `UsbfnDwc3Dxe`, `UsbDeviceDxe`, `UsbConfigDxe`, `UsbInitDxe`, `UsbPwrCtrlDxe`, plus EDK2 USB bus drivers. | The platform intends to use the vendor USB function stack. The actual driver implementation is not tracked here; the vendor package must be supplied to build the complete image. |
| USB host | The same lists reference Qualcomm XHCI drivers and EDK2 USB host/bus drivers. | Host support is declared, not hardware-validated. |
| IOMMU | The DXE lists reference `HALIOMMUDxe`. | This is a vendor DXE dependency. Its binary and runtime initialization cannot be verified from this repository alone. |
| Power / clocks | The lists reference Qualcomm Clock, RPMH, NPA, PwrUtils, VCS, ICB, SPMI and PMIC drivers. | These are declared dependencies. Their successful initialization and power-domain coverage require vendor binaries and device logs. |
| Serial / GENI | No Cupid-specific GENI Serial Engine driver is evidenced by the current Cupid DXE lists. | Do not add a guessed GENI driver or register map. First establish whether the reported message comes from this UEFI stage or another boot stage. |
| Loader / handoff | The platform contains UEFI configuration and memory-map code; the memory-map documentation explicitly marks HakiOS-added regions as provisional. | A message such as `no loader in memory` must be traced to the component that emits it. It is not fixed by adding an unrelated UEFI DXE entry. |

## Required evidence before implementation

1. Capture the complete boot log with stage boundaries and timestamps. Identify
   whether each message originates in XBL, UEFI/EDK2, HakiOS loader, or kernel.
2. Preserve the exact device-tree blob and record its SHA-256. Inspect the USB,
   PHY, power-domain, clock, and IOMMU nodes from that same blob.
3. Record the vendor UEFI driver inventory extracted from the user's own device.
   Do not commit proprietary vendor binaries or publish them in CI artifacts.
4. Match each driver's INF/module identity and dependencies against the pinned
   Mu-Silicium Waipio platform. Do not infer support from a filename alone.
5. Confirm the memory reservations against a known-good vendor boot log before
   changing any address in `MemoryMapLib` or the DSC.
6. Run static validation and a complete build with the matching vendor files.
   Then test on hardware using a recoverable, non-destructive boot path.

## Safe implementation order

- First: make the boot log attributable to a precise boot stage and driver.
- Second: verify that the required vendor USB/IOMMU/power modules are present
  and that their APRIORI ordering matches their real dependencies.
- Third: fix only demonstrated ordering, configuration, or missing-source
  issues. Do not add speculative MMIO addresses, compatible strings, clocks,
  resets, PHY tuning, or power-domain IDs.
- Fourth: validate the resulting image and test USB enumeration separately
  from USB host functionality.
- Finally: verify loader availability and memory handoff independently.

## Acceptance criteria

- The platform validation report passes.
- The UEFI image links with the matching vendor modules supplied privately.
- Build logs show the intended modules were included.
- Hardware logs demonstrate USB device enumeration and the expected Fastboot
  interface; a successful compile alone is insufficient.
- IOMMU and power initialization are confirmed by stage-specific logs.
- The loader is present at the documented handoff point and the memory map is
  confirmed against device evidence.

## Current limitation

This repository does not contain the proprietary Cupid UEFI driver binaries.
The current source therefore cannot independently prove the runtime behavior
of USB, IOMMU, power, or GENI. Keep those items marked unverified until the
matching vendor modules and device-side logs are available.
