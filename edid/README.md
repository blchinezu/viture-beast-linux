# edid - Viture Beast XR EDID Reference

Raw EDID dumps captured from the Viture Beast XR glasses in each display mode, plus scripts to build merged and overclocked EDID binaries.

This is provided for **reference and informational purposes**. The [udev fix](../udev/) does not require a custom EDID - the glasses' native EDID and built-in mode switching work fine with the udev rule on supported kernels.

A custom EDID may be useful if:
- Your system does not recognize one or more of the glasses' modes at all
- The glasses' USB-C renegotiation fails entirely (e.g., `EPROTO` / error -71 from the `typec_displayport` driver), preventing mode switching from working even partially
- You want to overclock the glasses beyond their stock 120 Hz / 60 Hz ultrawide modes
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

### `edid_viture_beast_overclock.bin`

An overclocked EDID binary (256 bytes, 2 blocks) containing all three original modes plus four overclocked modes. Built by `build_viture_beast_overclock_edid.py`. This is the file you would deploy to push the glasses beyond their stock refresh rates.

Modes included:

| DTD | Resolution | Refresh | Pixel Clock | Blanking | Notes |
|-----|-----------|---------|-------------|----------|-------|
| 1 | 1920x1080 | 60 Hz | 148.50 MHz | Standard CEA | Original, preferred |
| 2 | 1920x1080 | 120 Hz | 297.00 MHz | Standard CEA | Original |
| 3 | 3840x1080 | 60 Hz | 297.00 MHz | Standard | Original ultrawide |
| 4 | 1920x1080 | **130 Hz** | 321.75 MHz | Standard CEA | OC - fits RBR + YCbCr 4:2:2 |
| 5 | 3840x1080 | **65 Hz** | 321.75 MHz | Standard | OC - fits RBR + YCbCr 4:2:2 |
| 6 | 1920x1080 | **144 Hz** | 330.38 MHz | CVT-RB | OC - requires HBR link or above |
| 7 | 3840x1080 | **90 Hz** | 397.08 MHz | CVT-RB | OC - requires HBR2 link |

DTDs 4 and 5 use byte-for-byte identical blanking to the stock 120 Hz and ultrawide modes - only the pixel clock field changes (8.3% increase). This is the safest possible overclock: the scaler sees the exact same timing structure it already accepts, just clocked slightly faster.

DTDs 6 and 7 use CVT reduced blanking (160 px horizontal, 23 lines vertical) to keep pixel clocks manageable at higher refresh rates. These exceed RBR link bandwidth even at YCbCr 4:2:2, so they will only appear on systems where the DP link trains at HBR or above (e.g., Intel Thunderbolt, NVIDIA).

Range limits are updated to 56–144 Hz vertical, 50–160 kHz horizontal, 400 MHz max pixel clock. The HDMI VSDB max TMDS clock is updated to 400 MHz to match.

### `build_viture_beast_overclock_edid.py`

Python script that constructs `edid_viture_beast_overclock.bin`. No dependencies beyond Python 3. Optionally validates the output with `edid-decode` if installed.

```bash
python3 build_viture_beast_overclock_edid.py
```

### Inspecting EDID files

```bash
sudo apt install edid-decode
edid-decode edid_viture_beast_1080p_60hz.bin
```

## Overclocking background

### Why it might work

The Viture glasses' EDID declares a 300 MHz maximum pixel clock, but this is a firmware-imposed soft limit, not a hardware ceiling. The [Viture Pro XR has been successfully overclocked](https://github.com/DaniXmir/GlassVr) to **3840x1080@95Hz** (~420 MHz pixel clock) using Custom Resolution Utility (CRU) on Windows, running in YCbCr 4:2:2 at 8-bit. The overclock is firmware-dependent: older firmware (0.03.004) handles 95 Hz cleanly, while newer firmware (0.03.013) restricts to 60 Hz.

Since the Viture Beast is a newer/higher-end product likely using the same bridge chip family, it should have similar or better headroom above the declared 300 MHz limit.

### Bandwidth constraints

The overclocked modes are designed around the DP link bandwidth available on different systems:

| Link Rate | Effective BW (4 lanes, 8b/10b) | Max pixel clock @ YCbCr 4:2:2 (16 bpp) | Available OC modes |
|-----------|------|------|------|
| RBR (1.62 Gbps/lane) | 5.18 Gbps | ~324 MHz | 130 Hz, 65 Hz UW |
| HBR (2.70 Gbps/lane) | 8.64 Gbps | ~540 MHz | all modes |
| HBR2 (5.40 Gbps/lane) | 17.28 Gbps | ~1080 MHz | all modes |

On AMD systems using the [udev fix](../udev/) (forced 4-lane RBR + YCbCr 4:2:2), the 130 Hz and 65 Hz ultrawide modes fit within the link budget:

```
321.75 MHz × 16 bpp = 5148 Mbps  <  5184 Mbps (4-lane RBR)
```

On systems where HBR2 works natively (Intel Thunderbolt, NVIDIA), all seven modes should be available and the link is not a bottleneck.

### Theoretical maximums

Based on the Viture Pro XR's demonstrated ~420 MHz pixel clock ceiling:

| Mode | Standard blanking | CVT reduced blanking |
|------|-------------------|----------------------|
| 1920x1080 | ~170 Hz | ~191 Hz |
| 3840x1080 | ~85 Hz | ~95 Hz |

These are bridge-chip-limited estimates. The overclocked EDID includes conservative targets (130/144 Hz for 1080p, 65/90 Hz for ultrawide) that are well within this envelope.

### Risks

Overclocking the glasses is **experimental and unsupported**. Possible outcomes:
- The mode works perfectly (most likely for the standard-blanking 130 Hz / 65 Hz modes)
- The display shows artifacts or flickering (the scaler is borderline - try lowering the target)
- The display goes black (the scaler rejects the timing - switch back to a stock mode)
- In the worst case, a reboot with the override removed restores normal operation

There is no risk of permanent hardware damage from EDID-based overclocking - the glasses simply ignore signals they cannot handle, and the override is trivially reversible.

## Deploying an EDID override

Choose which EDID binary to deploy:
- `edid_viture_beast_all_modes.bin` - stock modes only (safe, for compatibility)
- `edid_viture_beast_overclock.bin` - stock + overclocked modes (experimental)

```bash
# Install the EDID binary
sudo mkdir -p /lib/firmware/edid
sudo cp edid_viture_beast_overclock.bin /lib/firmware/edid/

# Find your connector name
ls /sys/class/drm/

# Add kernel parameter - edit /etc/default/grub, append to GRUB_CMDLINE_LINUX:
#   drm.edid_firmware=DP-1:edid/edid_viture_beast_overclock.bin
# (replace DP-1 with your connector name)

sudo update-grub
sudo reboot
```

After reboot, the kernel will use the override EDID for that connector regardless of what EDID the connected device provides. All compatible modes will appear in your display settings (the driver automatically filters out modes that exceed the current link bandwidth). With the udev fix active, the overclocked modes will use YCbCr 4:2:2 encoding.

To remove the override, delete the `drm.edid_firmware` parameter from GRUB and reboot.
