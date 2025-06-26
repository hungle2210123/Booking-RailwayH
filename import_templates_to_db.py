#!/usr/bin/env python3
"""
Import message templates from JSON file to PostgreSQL database
"""
import json
import sys
import os

# Add the current directory to path to import Flask app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def import_templates():
    try:
        # Import Flask app and models
        from app_postgresql import app
        from core.models import MessageTemplate, db
        
        with app.app_context():
            # Read JSON templates
            with open('config/message_templates.json', 'r', encoding='utf-8') as f:
                templates = json.load(f)
            
            print(f"📋 Found {len(templates)} templates in JSON file")
            
            # Clear existing templates
            existing_count = MessageTemplate.query.count()
            if existing_count > 0:
                print(f"🗑️ Clearing {existing_count} existing templates")
                MessageTemplate.query.delete()
                db.session.commit()
            
            # Import templates with improved names
            imported_count = 0
            
            for template_data in templates:
                category = template_data.get('Category', 'General')
                label = template_data.get('Label', 'Unknown')
                message = template_data.get('Message', '')
                
                # Create better template names
                if label in ['DEFAULT', '1', '2', '3', '4', '1.', '2.']:
                    if category == 'WELCOME':
                        if label == '1.':
                            template_name = 'Standard Welcome'
                        elif label == '2.':
                            template_name = 'Arrival Time Request'
                        else:
                            template_name = 'General Welcome'
                    elif category == 'TAXI':
                        if label == '1':
                            template_name = 'Airport Pickup - Pillar 14'
                        elif label == '2':
                            template_name = 'Driver Booking Confirmation'
                        elif label == '3':
                            template_name = 'Taxi Service Offer'
                        else:
                            template_name = 'Taxi Information'
                    elif category == 'FEED BACK':
                        if 'bye bye' in label:
                            template_name = 'Farewell with Offers'
                        elif label == '3':
                            template_name = 'Apology with Discounts'
                        else:
                            template_name = 'Review Request'
                    elif label == 'DEFAULT':
                        template_name = f'{category} - Standard Message'
                    else:
                        template_name = f'{category} - Option {label}'
                else:
                    template_name = label
                
                # Create template record
                template = MessageTemplate(
                    template_name=template_name,
                    category=category,
                    template_content=message
                )
                
                db.session.add(template)
                imported_count += 1
            
            # Commit all changes
            db.session.commit()
            
            print(f"✅ Successfully imported {imported_count} templates to database")
            
            # Verify import
            final_count = MessageTemplate.query.count()
            print(f"📊 Database now contains {final_count} templates")
            
            # Show categories
            categories = db.session.query(MessageTemplate.category).distinct().all()
            category_list = [cat[0] for cat in categories]
            print(f"📂 Categories: {', '.join(category_list)}")
            
    except Exception as e:
        print(f"❌ Error importing templates: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import_templates()