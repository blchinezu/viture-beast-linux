# udev - Automatic DP Link Rate Management

Automatically locks the DisplayPort link rate when Viture Beast XR glasses are connected, and resets to auto-negotiation when they are disconnected.

## Files

### `99-viture-dp.rules`

The udev rule file. Install to `/etc/udev/rules.d/`.

Contains three rules that trigger the helper script:

1. **DRM change event** (`ACTION=="change", SUBSYSTEM=="drm"`) - fires when the DP link state changes. This catches the glasses' mode switch (which triggers a link renegotiation) and re-applies the forced setting before the driver can break it. Also fires on initial hotplug.

2. **USB add event** (`ACTION=="add", SUBSYSTEM=="usb"`) - fires when the Viture USB device (`35ca:1102`) appears. The glasses expose both a DP Alt Mode connection and a USB device (microphone). The USB device may enumerate after the DRM connector comes up, so this rule ensures the helper runs after the Viture is detectable.

3. **USB remove event** (`ACTION=="remove", SUBSYSTEM=="usb"`) - fires when the Viture USB device disappears (cable unplugged). Triggers the helper to reset link settings to auto-negotiation so other displays work normally.

The remove rule uses `ENV{ID_VENDOR_ID}` / `ENV{ID_MODEL_ID}` instead of `ATTR{idVendor}` / `ATTR{idProduct}` because device attributes are no longer available during removal - only udev environment variables (cached from the add event) persist.

### `viture-dp-helper`

The helper script. Install to `/usr/local/bin/`.

On every invocation, it checks whether the Viture USB device is currently present:

- **Viture present** (`lsusb -d 35ca:1102` succeeds): writes `4 0x6 0` to the amdgpu debugfs `link_settings` file, locking the DP link at 4-lane RBR.

- **Viture absent**: writes `0 0` to reset the link to auto-negotiation. Falls back to writing `4 0x14` (HBR2) if `0 0` is not accepted by the driver.

The script is idempotent - running it multiple times has no adverse effects.

## What it fixes

The amdgpu driver selects the DP link rate based on the preferred (initial) display mode. For the Viture glasses, this is 1080p@60Hz, which trains the link at RBR (1.62 Gbps per lane). When the user later switches to 120Hz or ultrawide (both requiring 297 MHz pixel clock), the driver attempts to retrain the link at a higher rate (HBR2). This retraining fails - the glasses report HBR2 support but the link does not actually train successfully at that rate through the USB-C connection. The driver does not fall back gracefully.

By explicitly locking the link at RBR via debugfs, the driver enters a "forced" mode where it knows retraining is not an option. It then correctly selects YCbCr 4:2:2 encoding (16bpp instead of 24bpp RGB), reducing the required bandwidth from 7.13 Gbps to 4.75 Gbps - which fits within the 5.18 Gbps effective capacity of a 4-lane RBR link.

Writing `4 0x6 0` even when the current value already reads `4 0x6 0` is intentional and necessary. The numeric values are the same, but the act of writing transitions the driver from "auto-negotiate" mode to "forced/locked" mode. These are distinct internal states with different behavior during mode switching.

## Why the glasses' mode switch causes problems

When you switch the glasses' mode via their built-in menu (e.g., from default to 120Hz), the glasses trigger a DisplayPort link state change. This manifests as a DRM change event in the kernel. In the driver's default auto-negotiate mode, this event can cause a link retraining attempt that fails and leaves the link in a degraded state - visible as glitching, artifacts, or signal loss.

The udev rule catches this DRM change event and re-applies the forced RBR setting, preventing the driver from attempting the failed retraining.

## Installation

```bash
sudo cp viture-dp-helper /usr/local/bin/
sudo chmod +x /usr/local/bin/viture-dp-helper
sudo cp 99-viture-dp.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
```

## Configuration

If your system uses a different DRM connector or DRI card number, update:

- `99-viture-dp.rules`: change `card1-DP-1` in the KERNEL match
- `viture-dp-helper`: change the `LINK` variable path

To find your connector:

```bash
ls /sys/class/drm/
find /sys/kernel/debug/dri/ -name link_settings
```

If your Viture glasses have a different USB VID/PID:

```bash
lsusb | grep -i viture
```

Update the `35ca:1102` references in both files.

## Uninstall

```bash
sudo rm /usr/local/bin/viture-dp-helper
sudo rm /etc/udev/rules.d/99-viture-dp.rules
sudo udevadm control --reload-rules
```
