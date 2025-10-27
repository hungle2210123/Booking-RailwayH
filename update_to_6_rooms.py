#!/usr/bin/env python3
"""
UPDATE TO 6 ROOMS SCRIPT
Updates all hardcoded capacity from 4 to 6 rooms across the codebase
Supports: 118 Hang Bac (4 rooms) + 18 Hang Be (2 rooms) = 6 total
"""

import re
import os

FILES_TO_UPDATE = [
    'app.py',
    'core/logic_postgresql.py',
]

REPLACEMENTS = [
    # Room capacity constants
    (r'MAX_ROOMS_PER_DAY\s*=\s*4', 'MAX_ROOMS_PER_DAY = 6'),
    (r'total_capacity:\s*int\s*=\s*4', 'total_capacity: int = 6'),
    (r'hotel_capacity.*4\s*rooms', 'hotel_capacity (6 rooms total: 118 Hang Bac=4, 18 Hang Be=2)'),

    # Comments and documentation
    (r'4 phòng', '6 phòng (118 Hang Bac=4, 18 Hang Be=2)'),
    (r'\(4 PHÒNG\)', '(6 PHÒNG TỔNG: 118 Hang Bac=4 + 18 Hang Be=2)'),
    (r'days with < 4 rooms', 'days with < 6 rooms'),
    (r'4-room hotel', '6-room hotel (2 properties)'),
]

def update_file(filepath):
    """Update a single file with all replacements"""
    full_path = f'/mnt/c/Users/T14/Desktop/hotel_flask_app/hotel_flask_app_optimized/{filepath}'

    if not os.path.exists(full_path):
        print(f"⚠️  File not found: {filepath}")
        return False

    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content
        changes_made = 0

        for pattern, replacement in REPLACEMENTS:
            matches = re.findall(pattern, content)
            if matches:
                content = re.sub(pattern, replacement, content)
                changes_made += len(matches)
                print(f"  ✅ Replaced {len(matches)}x: {pattern[:50]}...")

        if changes_made > 0:
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ Updated {filepath} ({changes_made} changes)")
            return True
        else:
            print(f"ℹ️  No changes needed in {filepath}")
            return False

    except Exception as e:
        print(f"❌ Error updating {filepath}: {e}")
        return False

def main():
    print("\n" + "="*60)
    print("🏨 UPDATING HOTEL CAPACITY: 4 → 6 ROOMS")
    print("="*60)
    print("Hotels:")
    print("  • 118 Hang Bac Hostel: 4 rooms (original)")
    print("  • 18 Hang Be Apartment: 2 rooms (NEW)")
    print("  • TOTAL CAPACITY: 6 rooms")
    print("="*60 + "\n")

    updated_files = 0

    for filepath in FILES_TO_UPDATE:
        print(f"\n📝 Processing: {filepath}")
        if update_file(filepath):
            updated_files += 1

    print("\n" + "="*60)
    print(f"✅ CAPACITY UPDATE COMPLETE!")
    print(f"   Files updated: {updated_files}/{len(FILES_TO_UPDATE)}")
    print("="*60)
    print("\nNext steps:")
    print("1. Test calendar capacity display (should show 6 rooms)")
    print("2. Add hotel selector dropdown to booking forms")
    print("3. Update dashboard filters for multi-hotel view")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
