# viture-beast-linux

Fix for Viture Beast XR glasses 120Hz and ultrawide modes breaking on Linux over USB-C DisplayPort Alt Mode.

## The problem

The Viture Beast XR glasses support three display modes selectable from their built-in menu:

| Mode | Resolution | Refresh Rate |
|------|-----------|-------------|
| Default | 1920x1080 | 60 Hz |
| 120 Hz | 1920x1080 | 120 Hz |
| Ultrawide | 3840x1080 | 60 Hz |

On some machines, switching to 120Hz or ultrawide via the glasses' menu causes the display to glitch, show artifacts, or go black entirely. The default 1080p@60Hz mode works fine.

This happens because the glasses' mode switch can trigger a DisplayPort link state change, and the amdgpu driver does not gracefully handle the transition. The driver locks the DP link at a low rate (RBR - 1.62 Gbps/lane) based on the initial 1080p@60Hz mode, and when a higher-bandwidth mode is selected, it attempts to retrain the link at a higher rate, fails, and does not fall back to using YCbCr 4:2:2 encoding (which would fit within the existing link capacity).

## The fix

A [udev rule](udev/) that automatically forces the DP link into a locked state when the glasses are connected. In locked mode, the driver skips the failed retraining attempt and instead uses YCbCr 4:2:2 color encoding, which reduces bandwidth enough for all three modes to fit within the existing 4-lane RBR link.

When the glasses are disconnected, the rule resets the link to auto-negotiation so other displays work normally.

### How it works

The glasses expose a USB device (`35ca:1102 VITURE Microphone`) alongside their DisplayPort connection. The udev rule detects this device and writes to the amdgpu debugfs interface to lock the DP link rate:

- **Glasses plugged in** → force `4 0x6 0` (4 lanes, RBR, locked)
- **Glasses unplugged** → reset to `0 0` (auto-negotiation)
- **Glasses mode switch** → DRM change event re-applies the forced setting

### Bandwidth math

Both 1080p@120Hz and 3840x1080@60Hz have a pixel clock of 297 MHz:

| Mode | Pixel Clock | RGB 24bpp | YCbCr 4:2:2 16bpp | 4x RBR (5.18 Gbps) |
|------|-----------|-----------|-------------------|---------------------|
| 1080p@60Hz | 148.5 MHz | 3.56 Gbps | 2.38 Gbps | fits at RGB |
| 1080p@120Hz | 297.0 MHz | 7.13 Gbps | 4.75 Gbps | fits at 4:2:2 only |
| 3840x1080@60Hz | 297.0 MHz | 7.13 Gbps | 4.75 Gbps | fits at 4:2:2 only |

## Installation

### Quick start

```bash
# Install the helper script
sudo cp udev/viture-dp-helper /usr/local/bin/
sudo chmod +x /usr/local/bin/viture-dp-helper

# Install the udev rule
sudo cp udev/99-viture-dp.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
```

### Configuration

The udev rule and helper script contain hardware-specific paths that may need adjustment for your system:

| Value | Default | How to find yours |
|-------|---------|-------------------|
| DRM connector | `card1-DP-1` | `ls /sys/class/drm/` |
| debugfs path | `/sys/kernel/debug/dri/1/DP-1/link_settings` | `find /sys/kernel/debug/dri/ -name link_settings` |
| Viture USB ID | `35ca:1102` | `lsusb \| grep -i viture` |

Edit `99-viture-dp.rules` (KERNEL match) and `viture-dp-helper` (LINK variable) if your system uses different values.

### Usage

1. Plug in the Viture glasses
2. Switch the glasses to the desired mode via their built-in menu (120Hz or ultrawide)
3. The matching resolution/refresh rate will appear in your display settings

When you unplug the glasses, the link settings reset automatically. Other displays plugged into the same port will work normally.

### Uninstall

```bash
sudo rm /usr/local/bin/viture-dp-helper
sudo rm /etc/udev/rules.d/99-viture-dp.rules
sudo udevadm control --reload-rules
```

## EDID reference

The [edid/](edid/) directory contains raw EDID dumps captured from the Viture Beast XR glasses in each of their three modes, plus a Python script that merges all three modes into a single EDID binary.

This is provided for **reference and informational purposes** - the udev fix does not require a custom EDID. It may be useful if your system does not recognize the glasses' modes at all, or if you need to override the EDID for other reasons (e.g., the glasses' USB-C renegotiation fails entirely with `EPROTO` errors on your USB-C controller). See the [EDID README](edid/README.md) for details.

## Tested hardware

| Machine | USB-C Controller | OS | Default 60Hz | 120Hz | Ultrawide | Notes |
|---------|-----------------|-----|:---:|:---:|:---:|-------|
| Lenovo Yoga Slim 7 14ARE05 | AMD UCSI (Renoir) | Ubuntu 25.10 | works | works with udev fix | works with udev fix | Ryzen 7 4800U, amdgpu, Wayland |
| ASUS ROG Strix G733CX | Intel Thunderbolt | Ubuntu 24.04 | works | works natively | works natively | i9-12950HX, no fix needed |
| Samsung Galaxy S23 Ultra | Qualcomm | Android | works | broken | broken | USB-C renegotiation fails with EPROTO |

## Troubleshooting

### Modes still glitch after installing the udev rule

Manually run the helper and check the link settings:

```bash
sudo /usr/local/bin/viture-dp-helper
sudo cat /sys/kernel/debug/dri/1/DP-1/link_settings
```

The `Current` line should show `4  0x6  0`. If it doesn't, check that the debugfs path in the helper script matches your system.

### debugfs path doesn't exist

- debugfs might not be mounted: `sudo mount -t debugfs none /sys/kernel/debug`
- The DRI card number might differ: `ls /sys/kernel/debug/dri/`
- The connector name might differ: `ls /sys/kernel/debug/dri/*/`

### Viture USB device not detected

Check your Viture's USB IDs: `lsusb | grep -i viture`. If the VID/PID differs from `35ca:1102`, update both the udev rule and the helper script.

### Other displays broken after using glasses

The forced link setting persists until the glasses are unplugged (which triggers the auto-reset). If you unplugged the glasses but another display is still stuck at a low refresh rate, manually reset:

```bash
echo "0 0" | sudo tee /sys/kernel/debug/dri/1/DP-1/link_settings
```

Then replug your display.
