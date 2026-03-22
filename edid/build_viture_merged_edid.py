#!/usr/bin/env python3
"""
Build a Viture-only merged EDID with all 3 glasses modes.

Modes:
  1920x1080@60Hz   (preferred)
  1920x1080@120Hz
  3840x1080@60Hz   (ultrawide)

Stays as close to the original Viture EDID as possible.
2 blocks: Base + CTA-861 (no DisplayID needed, all clocks <= 300 MHz).
"""

import subprocess
import os

OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'viture_all_modes.bin')


def edid_checksum(block):
    return (256 - sum(block[:127]) % 256) % 256


def build_base():
    b = bytearray(128)

    # Header
    b[0:8] = b'\x00\xFF\xFF\xFF\xFF\xFF\xFF\x00'

    # Manufacturer: VIT (same as original)
    b[8:10] = b'\x59\x34'

    # Product code (from Viture original)
    b[10:12] = b'\x20\x01'

    # Serial: none
    b[12:16] = b'\x00\x00\x00\x00'

    # Week 20, Year 2023 (same as original)
    b[16], b[17] = 0x14, 0x21

    # EDID 1.3 (same as original)
    b[18], b[19] = 0x01, 0x03

    # Digital display (same as original: 0x80)
    b[20] = 0x80

    # Physical size: 50 x 31 cm (same as original Viture)
    b[21], b[22] = 0x32, 0x1F

    # Gamma 2.20
    b[23] = 0x78

    # Features: 0x12 = non-RGB, preferred timing in 1st DTD (same as original)
    b[24] = 0x12

    # Color characteristics (same as original Viture)
    b[25:35] = bytes([0xED, 0x85, 0xA7, 0x54, 0x3E, 0xAE, 0x26, 0x0E, 0x50, 0x54])

    # Established timings: none
    b[35:38] = b'\x00\x00\x00'

    # Standard timings: unused
    for i in range(8):
        b[38 + i * 2] = 0x01
        b[39 + i * 2] = 0x01

    # DTD 1 (preferred): 1920x1080@60Hz - exact bytes from Viture 60Hz EDID
    b[54:72] = bytes([
        0x02, 0x3A, 0x80, 0x18, 0x71, 0x38, 0x2D, 0x40,
        0x58, 0x2C, 0x45, 0x00, 0x80, 0x38, 0x74, 0x00,
        0x00, 0x1E,
    ])

    # DTD 2: 1920x1080@120Hz - exact bytes from Viture 120Hz EDID
    b[72:90] = bytes([
        0x04, 0x74, 0x80, 0x18, 0x71, 0x38, 0x2D, 0x40,
        0x58, 0x2C, 0x45, 0x00, 0x80, 0x38, 0x74, 0x00,
        0x00, 0x1E,
    ])

    # Display Product Name: "VITURE Beast" (same as original)
    b[90:108] = bytes([
        0x00, 0x00, 0x00, 0xFC, 0x00,
        0x56, 0x49, 0x54, 0x55, 0x52, 0x45, 0x20,  # "VITURE "
        0x42, 0x65, 0x61, 0x73, 0x74,               # "Beast"
        0x0A,                                         # LF terminator
    ])

    # Display Range Limits (same as original Viture)
    # V: 56-120 Hz, H: 50-160 kHz, max clock: 300 MHz
    b[108:126] = bytes([
        0x00, 0x00, 0x00, 0xFD, 0x00,
        0x38,  # min V: 56 Hz
        0x78,  # max V: 120 Hz
        0x32,  # min H: 50 kHz
        0xA0,  # max H: 160 kHz
        0x1E,  # max clock: 300 MHz (30 x 10)
        0x00,  # default GTF
        0x0A, 0x20, 0x20, 0x20, 0x20, 0x20, 0x20,
    ])

    # 1 extension block (CTA only)
    b[126] = 0x01

    b[127] = edid_checksum(b)
    return bytes(b)


def build_cta():
    b = bytearray(128)

    b[0] = 0x02  # CTA-861 extension tag
    b[1] = 0x03  # Revision 3

    p = 4

    # Audio Data Block (tag 1) - same as original Viture
    b[p:p + 4] = bytes([0x23, 0x09, 0x07, 0x07])
    p += 4

    # Speaker Allocation (tag 4) - same as original Viture
    b[p:p + 4] = bytes([0x83, 0x01, 0x00, 0x00])
    p += 4

    # HDMI VSDB (tag 3) - same as original Viture
    b[p:p + 8] = bytes([
        0x67,
        0x03, 0x0C, 0x00,  # OUI 00-0C-03
        0x00, 0x00,         # phys addr 0.0.0.0
        0x00,               # flags
        0x3C,               # max TMDS: 300 MHz
    ])
    p += 8

    # DTD offset
    b[2] = p

    # Flags: basic audio, YCbCr 4:2:2, 0 native DTDs
    # (original Viture uses 0x54 but native count doesn't affect functionality)
    b[3] = 0x50

    # DTD: 3840x1080@60Hz - exact bytes from Viture ultrawide EDID
    b[p:p + 18] = bytes([
        0x04, 0x74, 0x00, 0x30, 0xF2, 0x38, 0x2D, 0x40,
        0xD0, 0x20, 0x45, 0x40, 0x00, 0x38, 0xF4, 0x00,
        0x00, 0x1E,
    ])
    p += 18

    b[127] = edid_checksum(b)
    return bytes(b)


def main():
    edid = build_base() + build_cta()

    with open(OUTPUT, 'wb') as f:
        f.write(edid)

    print(f"Wrote {OUTPUT}")
    print(f"Size: {len(edid)} bytes ({len(edid) // 128} blocks)")
    print()

    try:
        r = subprocess.run(['edid-decode', OUTPUT], capture_output=True, text=True)
        print(r.stdout)
        if r.stderr:
            print("--- stderr ---")
            print(r.stderr)
    except FileNotFoundError:
        print("edid-decode not found")


if __name__ == '__main__':
    main()
