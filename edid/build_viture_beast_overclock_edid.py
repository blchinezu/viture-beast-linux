#!/usr/bin/env python3
"""
Build an overclocked Viture Beast EDID with original + OC modes.

Original modes (verbatim timing bytes from Viture Beast hardware):
  DTD 1: 1920x1080@60Hz   (148.50 MHz, preferred)
  DTD 2: 1920x1080@120Hz  (297.00 MHz)
  DTD 3: 3840x1080@60Hz   (297.00 MHz, ultrawide)

Overclocked modes — safe for AMD RBR link (4-lane RBR + YCbCr 4:2:2 = 5184 Mbps):
  DTD 4: 1920x1080@130Hz  (321.75 MHz, standard CEA blanking)
  DTD 5: 3840x1080@65Hz   (321.75 MHz, standard blanking)

  These use identical blanking to the 120Hz / ultrawide originals — only the pixel
  clock changes.  This is the safest possible overclock: the scaler sees the exact
  same timing structure it already accepts, just clocked ~8% faster.

  Bandwidth at YCbCr 4:2:2 16bpp:
    321.75 MHz × 16 = 5148 Mbps  <  5184 Mbps (4-lane RBR)  ✓

Overclocked modes — require HBR or HBR2 (Intel TB / NVIDIA / working AMD link):
  DTD 6: 1920x1080@144Hz  (330.38 MHz, CVT reduced blanking)
  DTD 7: 3840x1080@90Hz   (397.08 MHz, CVT reduced blanking)

  These use CVT-RB timings (160px H blanking, 23-line V blanking) to keep
  pixel clocks manageable.  The Viture Pro XR has been proven to accept
  3840x1080@95Hz via CRU (~420 MHz), so the bridge chip family can handle
  these clocks.  These modes exceed RBR bandwidth even at 4:2:2, so they
  will only appear on systems where the DP link trains at HBR or above.

Range limits updated: 56-144 Hz vertical, 50-160 kHz horizontal, 400 MHz max clock.
2 blocks: Base + CTA-861 (256 bytes total).
"""

import subprocess
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT = os.path.join(SCRIPT_DIR, 'edid_viture_beast_overclock.bin')


def checksum(block: bytearray) -> int:
    """EDID block checksum: all 128 bytes must sum to 0 mod 256."""
    return (256 - sum(block[:127]) % 256) % 256


def build_base() -> bytes:
    b = bytearray(128)

    # ── Header ──
    b[0:8] = b'\x00\xFF\xFF\xFF\xFF\xFF\xFF\x00'

    # ── Vendor & Product ──
    b[8:10] = b'\x59\x34'          # Manufacturer: VIT
    b[10:12] = b'\x20\x01'         # Product code (original)
    b[12:16] = b'\x00\x00\x00\x00' # Serial: none
    b[16], b[17] = 0x14, 0x21      # Week 20, Year 2023

    # ── EDID version ──
    b[18], b[19] = 0x01, 0x03      # EDID 1.3

    # ── Basic display ──
    b[20] = 0x80                    # Digital display
    b[21], b[22] = 0x32, 0x1F      # Physical size: 50 cm × 31 cm
    b[23] = 0x78                    # Gamma 2.20
    b[24] = 0x12                    # Non-RGB, preferred timing in 1st DTD

    # ── Color characteristics (original Viture) ──
    b[25:35] = bytes([
        0xED, 0x85, 0xA7, 0x54, 0x3E, 0xAE, 0x26, 0x0E, 0x50, 0x54,
    ])

    # ── Established & standard timings: none ──
    b[35:38] = b'\x00\x00\x00'
    for i in range(8):
        b[38 + i * 2] = 0x01
        b[39 + i * 2] = 0x01

    # ── DTD 1: 1920×1080 @ 60 Hz  —  148.50 MHz ──
    # Verbatim from Viture Beast 60Hz EDID
    # H: 1920 + 88 front + 44 sync + 148 back = 2200 total
    # V: 1080 +  4 front +  5 sync +  36 back = 1125 total
    b[54:72] = bytes([
        0x02, 0x3A,  # pixel clock: 14850 × 10 kHz = 148.50 MHz
        0x80, 0x18, 0x71,  # H active=1920, H blank=280
        0x38, 0x2D, 0x40,  # V active=1080, V blank=45
        0x58, 0x2C, 0x45, 0x00,  # H front=88, H sync=44, V front=4, V sync=5
        0x80, 0x38, 0x74,  # image size 1920×1080 mm
        0x00, 0x00, 0x1E,  # no border, +H +V sync
    ])

    # ── DTD 2: 1920×1080 @ 120 Hz  —  297.00 MHz ──
    # Verbatim from Viture Beast 120Hz EDID
    # Same blanking as 60Hz, doubled pixel clock
    b[72:90] = bytes([
        0x04, 0x74,  # pixel clock: 29700 × 10 kHz = 297.00 MHz
        0x80, 0x18, 0x71,
        0x38, 0x2D, 0x40,
        0x58, 0x2C, 0x45, 0x00,
        0x80, 0x38, 0x74,
        0x00, 0x00, 0x1E,
    ])

    # ── Display Product Name: "VITURE Beast" ──
    b[90:108] = bytes([
        0x00, 0x00, 0x00, 0xFC, 0x00,
        0x56, 0x49, 0x54, 0x55, 0x52, 0x45, 0x20,  # "VITURE "
        0x42, 0x65, 0x61, 0x73, 0x74,                # "Beast"
        0x0A,
    ])

    # ── Display Range Limits ──
    # Updated: V 56–144 Hz, H 50–160 kHz, max clock 400 MHz
    b[108:126] = bytes([
        0x00, 0x00, 0x00, 0xFD, 0x00,
        0x38,  # min V:  56 Hz
        0x90,  # max V: 144 Hz  (was 120)
        0x32,  # min H:  50 kHz
        0xA0,  # max H: 160 kHz
        0x28,  # max clock: 400 MHz  (was 300)
        0x00,  # default GTF
        0x0A, 0x20, 0x20, 0x20, 0x20, 0x20, 0x20,
    ])

    # ── Extension count ──
    b[126] = 0x01  # 1 CTA extension block

    b[127] = checksum(b)
    return bytes(b)


def build_cta() -> bytes:
    b = bytearray(128)

    b[0] = 0x02  # CTA-861 extension tag
    b[1] = 0x03  # Revision 3

    p = 4  # data block area starts at byte 4

    # ── Audio Data Block (tag 1) — original Viture ──
    b[p:p + 4] = bytes([0x23, 0x09, 0x07, 0x07])
    p += 4

    # ── Speaker Allocation Data Block (tag 4) — original Viture ──
    b[p:p + 4] = bytes([0x83, 0x01, 0x00, 0x00])
    p += 4

    # ── HDMI VSDB (tag 3) — max TMDS updated to 400 MHz ──
    b[p:p + 8] = bytes([
        0x67,
        0x03, 0x0C, 0x00,  # OUI 00-0C-03 (HDMI)
        0x00, 0x00,         # phys addr 0.0.0.0
        0x00,               # flags
        0x50,               # max TMDS: 400 MHz (80 × 5)  (was 300)
    ])
    p += 8

    # ── DTD offset & flags ──
    b[2] = p   # DTDs start here
    b[3] = 0x50  # basic audio, YCbCr 4:2:2 supported, 0 native DTDs

    # ── DTD 3: 3840×1080 @ 60 Hz  —  297.00 MHz  (original ultrawide) ──
    # Verbatim from Viture Beast ultrawide EDID
    # H: 3840 + 464 front + 32 sync + 64 back = 4400 total
    # V: 1080 +   4 front +  5 sync + 36 back = 1125 total
    b[p:p + 18] = bytes([
        0x04, 0x74,  # pixel clock: 29700 × 10 kHz = 297.00 MHz
        0x00, 0x30, 0xF2,  # H active=3840, H blank=560
        0x38, 0x2D, 0x40,  # V active=1080, V blank=45
        0xD0, 0x20, 0x45, 0x40,  # H front=464, H sync=32, V front=4, V sync=5
        0x00, 0x38, 0xF4,  # image size 3840×1080 mm
        0x00, 0x00, 0x1E,
    ])
    p += 18

    # ── DTD 4: 1920×1080 @ 130 Hz  —  321.75 MHz  (OC, standard blanking) ──
    # Identical timing to DTD 2 (120 Hz), only pixel clock raised.
    # 2200 × 1125 × 130 = 321,750,000 Hz → 32175 × 10 kHz = 0x7DAF
    # BW @ 4:2:2: 321.75 × 16 = 5148 Mbps < 5184 (4-lane RBR)
    b[p:p + 18] = bytes([
        0xAF, 0x7D,  # pixel clock: 321.75 MHz
        0x80, 0x18, 0x71,
        0x38, 0x2D, 0x40,
        0x58, 0x2C, 0x45, 0x00,
        0x80, 0x38, 0x74,
        0x00, 0x00, 0x1E,
    ])
    p += 18

    # ── DTD 5: 3840×1080 @ 65 Hz  —  321.75 MHz  (OC, standard blanking) ──
    # Identical timing to DTD 3 (UW 60 Hz), only pixel clock raised.
    # 4400 × 1125 × 65 = 321,750,000 Hz → 32175 × 10 kHz = 0x7DAF
    # BW @ 4:2:2: same as DTD 4
    b[p:p + 18] = bytes([
        0xAF, 0x7D,  # pixel clock: 321.75 MHz
        0x00, 0x30, 0xF2,
        0x38, 0x2D, 0x40,
        0xD0, 0x20, 0x45, 0x40,
        0x00, 0x38, 0xF4,
        0x00, 0x00, 0x1E,
    ])
    p += 18

    # ── DTD 6: 1920×1080 @ 144 Hz  —  330.38 MHz  (OC, CVT-RB) ──
    # CVT reduced blanking:
    # H: 1920 + 48 front + 32 sync + 80 back = 2080 total (160 blank)
    # V: 1080 +  3 front +  5 sync + 15 back = 1103 total  (23 blank)
    # 2080 × 1103 × 144 ≈ 330,380,000 Hz → 33038 × 10 kHz = 0x810E
    # Exceeds RBR 4:2:2 budget — requires HBR link or above.
    b[p:p + 18] = bytes([
        0x0E, 0x81,  # pixel clock: 330.38 MHz
        0x80, 0xA0, 0x70,  # H active=1920, H blank=160
        0x38, 0x17, 0x40,  # V active=1080, V blank=23
        0x30, 0x20, 0x35, 0x00,  # H front=48, H sync=32, V front=3, V sync=5
        0x80, 0x38, 0x74,  # image size 1920×1080 mm
        0x00, 0x00, 0x1E,
    ])
    p += 18

    # ── DTD 7: 3840×1080 @ 90 Hz  —  397.08 MHz  (OC, CVT-RB) ──
    # CVT reduced blanking:
    # H: 3840 + 48 front + 32 sync + 80 back = 4000 total (160 blank)
    # V: 1080 +  3 front +  5 sync + 15 back = 1103 total  (23 blank)
    # 4000 × 1103 × 90 = 397,080,000 Hz → 39708 × 10 kHz = 0x9B1C
    # Requires HBR2 or above.
    b[p:p + 18] = bytes([
        0x1C, 0x9B,  # pixel clock: 397.08 MHz
        0x00, 0xA0, 0xF0,  # H active=3840, H blank=160
        0x38, 0x17, 0x40,  # V active=1080, V blank=23
        0x30, 0x20, 0x35, 0x00,  # H front=48, H sync=32, V front=3, V sync=5
        0x00, 0x38, 0xF4,  # image size 3840×1080 mm
        0x00, 0x00, 0x1E,
    ])
    p += 18

    # remaining bytes stay 0x00 (padding)

    b[127] = checksum(b)
    return bytes(b)


def main():
    edid = build_base() + build_cta()

    with open(OUTPUT, 'wb') as f:
        f.write(edid)

    print(f"Wrote {OUTPUT}")
    print(f"Size: {len(edid)} bytes ({len(edid) // 128} blocks)")
    print()

    # ── Mode summary ──
    modes = [
        ("DTD 1", "1920x1080 @  60 Hz", "148.50 MHz", "standard CEA",   "original — preferred"),
        ("DTD 2", "1920x1080 @ 120 Hz", "297.00 MHz", "standard CEA",   "original"),
        ("DTD 3", "3840x1080 @  60 Hz", "297.00 MHz", "standard",       "original ultrawide"),
        ("DTD 4", "1920x1080 @ 130 Hz", "321.75 MHz", "standard CEA",   "OC — fits RBR 4:2:2"),
        ("DTD 5", "3840x1080 @  65 Hz", "321.75 MHz", "standard",       "OC — fits RBR 4:2:2"),
        ("DTD 6", "1920x1080 @ 144 Hz", "330.38 MHz", "CVT-RB",        "OC — needs HBR+"),
        ("DTD 7", "3840x1080 @  90 Hz", "397.08 MHz", "CVT-RB",        "OC — needs HBR2"),
    ]
    print("Modes:")
    for dtd, res, clk, timing, note in modes:
        print(f"  {dtd}:  {res}  {clk:>11s}  ({timing:12s})  {note}")
    print()

    # ── Validate with edid-decode ──
    try:
        r = subprocess.run(['edid-decode', OUTPUT], capture_output=True, text=True)
        print(r.stdout)
        if r.stderr:
            print("--- stderr ---")
            print(r.stderr)
    except FileNotFoundError:
        print("(edid-decode not found — install with: sudo apt install edid-decode)")


if __name__ == '__main__':
    main()
