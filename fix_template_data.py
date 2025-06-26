#!/usr/bin/env python3
"""
Fix PostgreSQL template_name column data - Map Excel Labels to template_name correctly
"""
import json
import os
import sys

def create_template_fix_sql():
    """Create SQL script to fix template data based on JSON mapping"""
    try:
        # Read the JSON template file to get correct Label → Content mapping
        json_file_path = 'config/message_templates.json'
        
        if not os.path.exists(json_file_path):
            print(f"❌ JSON template file not found at {json_file_path}")
            return
        
        with open(json_file_path, 'r', encoding='utf-8') as f:
            templates = json.load(f)
        
        print(f"📋 Found {len(templates)} templates in JSON file")
        
        # Create SQL script to fix the data
        sql_script = """-- Fix template_name column data in PostgreSQL
-- This script corrects the mapping: Label → template_name, Message → template_content

BEGIN;

-- Clear existing templates first
DELETE FROM message_templates;

-- Insert templates with CORRECT field mapping
"""
        
        template_id = 1
        for template_data in templates:
            category = template_data.get('Category', 'General')
            label = template_data.get('Label', 'Unknown')  # This should go to template_name
            message = template_data.get('Message', '')     # This should go to template_content
            
            # Escape single quotes in SQL
            category_escaped = category.replace("'", "''")
            label_escaped = label.replace("'", "''")
            message_escaped = message.replace("'", "''")
            
            # Create better display names while keeping original labels
            display_name = label
            if label in ['DEFAULT', '1', '2', '3', '4', '1.', '2.']:
                if category == 'WELCOME':
                    if label == '1.':
                        display_name = 'Standard Welcome'
                    elif label == '2.':
                        display_name = 'Arrival Time Request'
                    else:
                        display_name = f'Welcome Message {label}'
                elif category == 'TAXI':
                    if label == '1':
                        display_name = 'Airport Pickup - Pillar 14'
                    elif label == '2':
                        display_name = 'Driver Booking Confirmation'
                    elif label == '3':
                        display_name = 'Taxi Service Offer'
                    else:
                        display_name = f'Taxi Message {label}'
                elif category == 'FEED BACK':
                    if label == '3':
                        display_name = 'Apology with Discounts'
                    elif 'bye' in label.lower():
                        display_name = 'Farewell Message'
                    else:
                        display_name = f'Feedback Message {label}'
                elif category == 'CHECK IN':
                    display_name = f'Check-in Instructions {label}'
                elif category == 'ARRIVAL':
                    display_name = f'Arrival Information {label}'
                else:
                    display_name = f'{category} - {label}'
            
            # Add SQL INSERT statement
            sql_script += f"""
INSERT INTO message_templates (template_id, template_name, category, template_content, created_at, updated_at)
VALUES ({template_id}, '{display_name}', '{category_escaped}', '{message_escaped}', NOW(), NOW());
"""
            template_id += 1
        
        sql_script += """
-- Reset sequence to continue from last ID
SELECT setval('message_templates_template_id_seq', (SELECT MAX(template_id) FROM message_templates));

COMMIT;

-- Verify the fix
SELECT template_id, template_name, category, 
       CASE WHEN LENGTH(template_content) > 50 
            THEN SUBSTRING(template_content, 1, 50) || '...' 
            ELSE template_content 
       END as content_preview
FROM message_templates 
ORDER BY category, template_name 
LIMIT 20;
"""
        
        # Write SQL script to file
        sql_file_path = 'fix_template_data.sql'
        with open(sql_file_path, 'w', encoding='utf-8') as f:
            f.write(sql_script)
        
        print(f"✅ Created SQL fix script: {sql_file_path}")
        print(f"📊 Script will fix {len(templates)} templates")
        
        # Show sample of what will be fixed
        print("\n📋 Sample of corrections that will be made:")
        for i, template_data in enumerate(templates[:5]):
            category = template_data.get('Category', 'General')
            label = template_data.get('Label', 'Unknown')
            message = template_data.get('Message', '')
            
            print(f"  {i+1}. Category: '{category}' | Label: '{label}' | Content: '{message[:50]}...'")
        
        print(f"\n🚀 To apply the fix, run:")
        print(f"   psql -d your_database_name -f {sql_file_path}")
        
        return sql_file_path
        
    except Exception as e:
        print(f"❌ Error creating template fix: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    create_template_fix_sql()