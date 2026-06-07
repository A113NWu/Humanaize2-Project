#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Create a simple icon file for Humanaize 2.0 Agent
"""

import struct

def create_simple_icon():
    # Create a minimal 16x16 32-bit icon
    width = 16
    height = 16
    bit_count = 32
    
    # Create simple gradient icon data (BGRA format)
    icon_data = bytearray()
    for y in range(height):
        for x in range(width):
            # Simple blue gradient
            alpha = 255
            red = int(50 + (x / width) * 100)
            green = int(100 + (y / height) * 100)
            blue = 200
            icon_data.extend([blue, green, red, alpha])
    
    # BITMAPINFOHEADER (40 bytes)
    info_header = struct.pack('<IIIHHIIIIII',
        40,  # Header size
        width,
        height * 2,  # Total height (XOR + AND masks)
        1,  # Planes
        bit_count,
        0,  # Compression (BI_RGB)
        len(icon_data),  # Size of bitmap data
        0, 0,  # XPelsPerMeter, YPelsPerMeter
        0, 0  # Colors used, Colors important
    )
    
    # Icon directory entry (16 bytes)
    dir_entry = struct.pack('<BBBBHHII',
        width, height,
        0,  # Colors in palette (0 for 32-bit)
        0,  # Reserved
        1,  # Planes
        bit_count,
        len(info_header) + len(icon_data),
        22  # Offset to bitmap data (6 + 16)
    )
    
    # ICONDIR header (6 bytes)
    icondir = struct.pack('<HHH',
        0,  # Reserved
        1,  # Type (1 = icon)
        1   # Count
    )
    
    icon_file = icondir + dir_entry + info_header + bytes(icon_data)
    
    with open('icon.ico', 'wb') as f:
        f.write(icon_file)
    
    print("Icon created: icon.ico")

if __name__ == "__main__":
    create_simple_icon()