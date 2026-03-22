# edid - Viture Beast XR EDID Reference

Raw EDID dumps captured from the Viture Beast XR glasses in each display mode, plus a script to build a merged EDID containing all three modes in a single binary.

This is provided for **reference and informational purposes**. The [udev fix](../udev/) does not require a custom EDID - the glasses' native EDID and built-in mode switching work fine with the udev rule on supported kernels.

A custom EDID may be useful if:
- Your system does not recognize one or more of the glasses' modes at all
- The glasses' USB-C renegotiation fails entirely (e.g., `EPROTO` / error -71 from the `typec_displayport` driver), preventing mode switching from working even partially
- You want to study the glasses' timing parameters

## Files

### Raw EDID dumps

Captured from the glasses on an ASUS ROG Strix G733CX (Intel Thunderbolt), where all three modes work natively. Each file is a 256-byte EDID binary (base block + CTA-861 extension).

| File | Glasses mode | Resolution | Pixel Clock |
|------|-------------|-----------|------------|
| `edid_viture_beast_1080p_60hz.bin` | Default | 1920x1080@60Hz | 148.50 MHz |
| `edid_viture_beast_1080p_120hz.bin` | 120 Hz | 1920x1080@120Hz | 297.00 MHz |
| `edid_viture_beast_3840x1080_60hz.bin` | Ultrawide | 3840x1080@60Hz | 297.00 MHz |

Each file is the complete EDID the glasses present when set to that mode. The glasses change their EDID on mode switch - the three files have different Detailed Timing Descriptors (DTDs), product codes, and physical dimensions.

### `edid_viture_beast_all_modes.bin`

A merged EDID binary (256 bytes, 2 blocks) containing all three modes in a single file. Built by `build_viture_merged_edid.py`. This is the file you would deploy as an EDID override if needed.

Modes included:
- 1920x1080@60Hz (DTD 1, preferred)
- 1920x1080@120Hz (DTD 2)
- 3840x1080@60Hz (DTD 3, in CTA extension)

All timing bytes are copied verbatim from the original per-mode EDIDs. The merged EDID preserves the original Viture manufacturer ID, product code, physical dimensions, color characteristics, range limits (56-120 Hz, 300 MHz max), and CTA data blocks (audio, speaker allocation, HDMI VSDB).

### `build_viture_merged_edid.py`

Python script that constructs `edid_viture_beast_all_modes.bin` from hardcoded timing bytes. No dependencies beyond Python 3. Optionally validates the output with `edid-decode` if installed.

```bash
python3 build_viture_merged_edid.py
```

Output:
```
Wrote .../edid_viture_beast_all_modes.bin
Size: 256 bytes (2 blocks)
```

To inspect any EDID file:

```bash
sudo apt install edid-decode
edid-decode edid_viture_beast_1080p_60hz.bin
```

## Deploying an EDID override

If you need the merged EDID as a kernel-level override:

```bash
# Install the EDID binary
sudo mkdir -p /lib/firmware/edid
sudo cp edid_viture_beast_all_modes.bin /lib/firmware/edid/

# Find your connector name
ls /sys/class/drm/

# Add kernel parameter - edit /etc/default/grub, append to GRUB_CMDLINE_LINUX:
#   drm.edid_firmware=DP-1:edid/edid_viture_beast_all_modes.bin
# (replace DP-1 with your connector name)

sudo update-grub
sudo reboot
```

After reboot, the kernel will use the merged EDID for that connector regardless of what EDID the connected device provides. All three modes will appear in your display settings. To remove the override, delete the `drm.edid_firmware` parameter and reboot.
