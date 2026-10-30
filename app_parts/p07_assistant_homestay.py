# p07_assistant_homestay — /ai_assistant page, homestay setup, quick notes, arrival times, hidden guests, no-show
# Part of app.py (lines 8547-9612 before the Oct 25 split). Runs inside app.py's namespace
# (see the loader at the end of app.py): every name defined in app.py and earlier parts is available here.
# AI Assistant - Message Templates (Mẫu câu)
@app.route('/ai_assistant')
def ai_assistant():
    """AI Assistant - Message Template Manager"""
    return render_template('ai_assistant.html')

# =====================================================
# HOMESTAY SETUP TRACKER ROUTES
# =====================================================
@app.route('/homestay_setup')
def homestay_setup():
    """Homestay Setup Tracker interface"""
    return render_template('homestay_setup.html')

@app.route('/api/homestay/properties', methods=['GET', 'POST'])
def homestay_properties_api():
    """Get all properties or create new property"""
    if request.method == 'GET':
        try:
            from core.models import HomestayProperty
            properties = HomestayProperty.query.order_by(HomestayProperty.created_at.desc()).all()
            return jsonify({
                'success': True,
                'properties': [p.to_dict() for p in properties]
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    elif request.method == 'POST':
        try:
            from core.models import HomestayProperty, db
            data = request.json

            new_property = HomestayProperty(
                property_name=data['property_name'],
                property_address=data.get('property_address'),
                property_type=data.get('property_type'),
                total_budget=data.get('total_budget', 0),
                budget_currency=data.get('budget_currency', 'VND'),
                setup_status=data.get('setup_status', 'planning'),
                start_date=datetime.strptime(data['start_date'], '%Y-%m-%d').date() if data.get('start_date') else None,
                target_completion_date=datetime.strptime(data['target_completion_date'], '%Y-%m-%d').date() if data.get('target_completion_date') else None,
                notes=data.get('notes')
            )

            db.session.add(new_property)
            db.session.commit()

            return jsonify({
                'success': True,
                'property': new_property.to_dict(),
                'message': 'Property created successfully'
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/homestay/properties/<int:property_id>', methods=['GET', 'PUT', 'DELETE'])
def homestay_property_detail(property_id):
    """Get, update, or delete a specific property"""
    from core.models import HomestayProperty, db

    property_obj = HomestayProperty.query.get_or_404(property_id)

    if request.method == 'GET':
        return jsonify({
            'success': True,
            'property': property_obj.to_dict()
        })

    elif request.method == 'PUT':
        try:
            data = request.json

            if 'property_name' in data:
                property_obj.property_name = data['property_name']
            if 'property_address' in data:
                property_obj.property_address = data['property_address']
            if 'property_type' in data:
                property_obj.property_type = data['property_type']
            if 'total_budget' in data:
                property_obj.total_budget = data['total_budget']
            if 'setup_status' in data:
                property_obj.setup_status = data['setup_status']
            if 'start_date' in data:
                property_obj.start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date() if data['start_date'] else None
            if 'target_completion_date' in data:
                property_obj.target_completion_date = datetime.strptime(data['target_completion_date'], '%Y-%m-%d').date() if data['target_completion_date'] else None
            if 'actual_completion_date' in data:
                property_obj.actual_completion_date = datetime.strptime(data['actual_completion_date'], '%Y-%m-%d').date() if data['actual_completion_date'] else None
            if 'notes' in data:
                property_obj.notes = data['notes']

            db.session.commit()

            return jsonify({
                'success': True,
                'property': property_obj.to_dict(),
                'message': 'Property updated successfully'
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': str(e)}), 500

    elif request.method == 'DELETE':
        try:
            db.session.delete(property_obj)
            db.session.commit()

            return jsonify({
                'success': True,
                'message': 'Property deleted successfully'
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/homestay/purchases', methods=['GET', 'POST'])
def homestay_purchases_api():
    """Get all purchases or create new purchase"""
    if request.method == 'GET':
        try:
            from core.models import PurchaseRecord
            property_id = request.args.get('property_id', type=int)

            query = PurchaseRecord.query
            if property_id:
                query = query.filter_by(property_id=property_id)

            purchases = query.order_by(PurchaseRecord.created_at.desc()).all()

            return jsonify({
                'success': True,
                'purchases': [p.to_dict() for p in purchases]
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    elif request.method == 'POST':
        try:
            from core.models import PurchaseRecord, db
            data = request.json

            quantity = int(data.get('quantity', 1))
            unit_price = float(data['unit_price'])
            total_price = quantity * unit_price

            new_purchase = PurchaseRecord(
                property_id=data['property_id'],
                template_id=data.get('template_id'),
                item_name=data['item_name'],
                item_category=data['item_category'],
                quantity=quantity,
                unit_price=unit_price,
                total_price=total_price,
                currency=data.get('currency', 'VND'),
                purchase_link=data.get('purchase_link'),
                vendor_name=data.get('vendor_name'),
                brand_name=data.get('brand_name'),
                purchase_status=data.get('purchase_status', 'planned'),
                purchase_date=datetime.strptime(data['purchase_date'], '%Y-%m-%d').date() if data.get('purchase_date') else None,
                delivery_date=datetime.strptime(data['delivery_date'], '%Y-%m-%d').date() if data.get('delivery_date') else None,
                notes=data.get('notes'),
                invoice_number=data.get('invoice_number'),
                warranty_info=data.get('warranty_info')
            )

            db.session.add(new_purchase)
            db.session.commit()

            return jsonify({
                'success': True,
                'purchase': new_purchase.to_dict(),
                'message': 'Purchase recorded successfully'
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/homestay/purchases/<int:purchase_id>', methods=['GET', 'PUT', 'DELETE'])
def homestay_purchase_detail(purchase_id):
    """Get, update, or delete a specific purchase"""
    from core.models import PurchaseRecord, db

    purchase = PurchaseRecord.query.get_or_404(purchase_id)

    if request.method == 'GET':
        return jsonify({
            'success': True,
            'purchase': purchase.to_dict()
        })

    elif request.method == 'PUT':
        try:
            data = request.json

            if 'item_name' in data:
                purchase.item_name = data['item_name']
            if 'item_category' in data:
                purchase.item_category = data['item_category']
            if 'quantity' in data or 'unit_price' in data:
                purchase.quantity = int(data.get('quantity', purchase.quantity))
                purchase.unit_price = float(data.get('unit_price', purchase.unit_price))
                purchase.total_price = purchase.quantity * purchase.unit_price
            if 'purchase_link' in data:
                purchase.purchase_link = data['purchase_link']
            if 'vendor_name' in data:
                purchase.vendor_name = data['vendor_name']
            if 'brand_name' in data:
                purchase.brand_name = data['brand_name']
            if 'purchase_status' in data:
                purchase.purchase_status = data['purchase_status']
            if 'purchase_date' in data:
                purchase.purchase_date = datetime.strptime(data['purchase_date'], '%Y-%m-%d').date() if data['purchase_date'] else None
            if 'delivery_date' in data:
                purchase.delivery_date = datetime.strptime(data['delivery_date'], '%Y-%m-%d').date() if data['delivery_date'] else None
            if 'installation_date' in data:
                purchase.installation_date = datetime.strptime(data['installation_date'], '%Y-%m-%d').date() if data['installation_date'] else None
            if 'notes' in data:
                purchase.notes = data['notes']
            if 'invoice_number' in data:
                purchase.invoice_number = data['invoice_number']
            if 'warranty_info' in data:
                purchase.warranty_info = data['warranty_info']

            db.session.commit()

            return jsonify({
                'success': True,
                'purchase': purchase.to_dict(),
                'message': 'Purchase updated successfully'
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': str(e)}), 500

    elif request.method == 'DELETE':
        try:
            db.session.delete(purchase)
            db.session.commit()

            return jsonify({
                'success': True,
                'message': 'Purchase deleted successfully'
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/homestay/templates', methods=['GET', 'POST'])
def homestay_templates_api():
    """Get all item templates or create new template"""
    if request.method == 'GET':
        try:
            from core.models import SetupItemTemplate
            category = request.args.get('category')

            query = SetupItemTemplate.query
            if category:
                query = query.filter_by(item_category=category)

            templates = query.order_by(SetupItemTemplate.item_category, SetupItemTemplate.item_name).all()

            return jsonify({
                'success': True,
                'templates': [t.to_dict() for t in templates]
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    elif request.method == 'POST':
        try:
            from core.models import SetupItemTemplate, db
            data = request.json

            new_template = SetupItemTemplate(
                item_name=data['item_name'],
                item_category=data['item_category'],
                item_subcategory=data.get('item_subcategory'),
                default_quantity=data.get('default_quantity', 1),
                estimated_price=data.get('estimated_price'),
                price_currency=data.get('price_currency', 'VND'),
                description=data.get('description'),
                specifications=data.get('specifications'),
                priority=data.get('priority', 'medium'),
                is_required=data.get('is_required', True),
                recommended_link=data.get('recommended_link'),
                recommended_brand=data.get('recommended_brand')
            )

            db.session.add(new_template)
            db.session.commit()

            return jsonify({
                'success': True,
                'template': new_template.to_dict(),
                'message': 'Template created successfully'
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/homestay/analytics/<int:property_id>', methods=['GET'])
def homestay_analytics(property_id):
    """Get analytics for a specific property"""
    try:
        from core.models import HomestayProperty, PurchaseRecord
        from sqlalchemy import func

        property_obj = HomestayProperty.query.get_or_404(property_id)

        # Calculate totals by category
        category_totals = db.session.query(
            PurchaseRecord.item_category,
            func.sum(PurchaseRecord.total_price).label('total'),
            func.count(PurchaseRecord.purchase_id).label('count')
        ).filter_by(property_id=property_id).group_by(PurchaseRecord.item_category).all()

        # Calculate totals by status
        status_totals = db.session.query(
            PurchaseRecord.purchase_status,
            func.sum(PurchaseRecord.total_price).label('total'),
            func.count(PurchaseRecord.purchase_id).label('count')
        ).filter_by(property_id=property_id).group_by(PurchaseRecord.purchase_status).all()

        # Grand total
        grand_total = db.session.query(
            func.sum(PurchaseRecord.total_price)
        ).filter_by(property_id=property_id).scalar() or 0

        return jsonify({
            'success': True,
            'property': property_obj.to_dict(),
            'analytics': {
                'by_category': [
                    {'category': cat, 'total': float(total), 'count': count}
                    for cat, total, count in category_totals
                ],
                'by_status': [
                    {'status': status, 'total': float(total), 'count': count}
                    for status, total, count in status_totals
                ],
                'grand_total': float(grand_total),
                'budget_remaining': float(property_obj.total_budget) - float(grand_total),
                'budget_used_percent': (float(grand_total) / float(property_obj.total_budget) * 100) if property_obj.total_budget > 0 else 0
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/homestay/images/upload', methods=['POST'])
def upload_homestay_images():
    """Upload product images with AI processing"""
    try:
        from core.models import HomestayItemImage, db
        import base64
        from PIL import Image
        import io

        property_id = request.form.get('property_id', type=int)
        if not property_id:
            return jsonify({'success': False, 'error': 'Property ID required'}), 400

        uploaded_images = []
        files = request.files.getlist('images')

        for file in files:
            if file and file.filename:
                # Read image data
                image_data = file.read()

                # Create image record
                image_record = HomestayItemImage(
                    property_id=property_id,
                    image_data=image_data,
                    image_filename=file.filename,
                    image_mimetype=file.mimetype,
                    is_processed=False
                )

                db.session.add(image_record)
                db.session.flush()  # Get image_id

                # Process with AI in background (async)
                try:
                    ai_metadata = process_product_image_with_ai(image_data)
                    if ai_metadata:
                        image_record.ai_title = ai_metadata.get('title')
                        image_record.ai_category = ai_metadata.get('category')
                        image_record.ai_vendor = ai_metadata.get('vendor')
                        image_record.ai_price = ai_metadata.get('price')
                        image_record.ai_description = ai_metadata.get('description')
                        image_record.ai_tags = ai_metadata.get('tags')
                        image_record.is_processed = True
                except Exception as ai_error:
                    image_record.processing_error = str(ai_error)
                    image_record.is_processed = False

                uploaded_images.append(image_record.to_dict())

        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'{len(uploaded_images)} images uploaded and processed',
            'images': uploaded_images
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/homestay/images', methods=['GET'])
def get_homestay_images():
    """Get all uploaded product images"""
    try:
        from core.models import HomestayItemImage

        property_id = request.args.get('property_id', type=int)
        search = request.args.get('search', '').strip()
        category = request.args.get('category', '').strip()

        query = HomestayItemImage.query

        if property_id:
            query = query.filter_by(property_id=property_id)

        if category and category != 'all':
            query = query.filter_by(ai_category=category)

        if search:
            search_term = f'%{search}%'
            query = query.filter(
                db.or_(
                    HomestayItemImage.ai_title.ilike(search_term),
                    HomestayItemImage.ai_vendor.ilike(search_term),
                    HomestayItemImage.ai_tags.ilike(search_term),
                    HomestayItemImage.manual_title.ilike(search_term)
                )
            )

        images = query.filter_by(is_converted=False).order_by(HomestayItemImage.created_at.desc()).all()

        return jsonify({
            'success': True,
            'images': [img.to_dict() for img in images],
            'total': len(images)
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/homestay/images/<int:image_id>', methods=['GET', 'PUT', 'DELETE'])
def homestay_image_detail(image_id):
    """Get, update, or delete image"""
    from core.models import HomestayItemImage, db

    image = HomestayItemImage.query.get_or_404(image_id)

    if request.method == 'GET':
        # Return actual image data
        if request.args.get('download') == 'true':
            return send_file(
                io.BytesIO(image.image_data),
                mimetype=image.image_mimetype,
                as_attachment=False,
                download_name=image.image_filename
            )
        return jsonify({
            'success': True,
            'image': image.to_dict()
        })

    elif request.method == 'PUT':
        try:
            data = request.json

            if 'manual_title' in data:
                image.manual_title = data['manual_title']
            if 'manual_vendor' in data:
                image.manual_vendor = data['manual_vendor']
            if 'manual_price' in data:
                image.manual_price = data['manual_price']
            if 'manual_notes' in data:
                image.manual_notes = data['manual_notes']

            db.session.commit()

            return jsonify({
                'success': True,
                'image': image.to_dict(),
                'message': 'Image updated successfully'
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': str(e)}), 500

    elif request.method == 'DELETE':
        try:
            db.session.delete(image)
            db.session.commit()

            return jsonify({
                'success': True,
                'message': 'Image deleted successfully'
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/homestay/images/<int:image_id>/convert', methods=['POST'])
def convert_image_to_purchase(image_id):
    """Convert image to purchase record"""
    try:
        from core.models import HomestayItemImage, PurchaseRecord, db

        image = HomestayItemImage.query.get_or_404(image_id)

        if image.is_converted:
            return jsonify({'success': False, 'error': 'Image already converted'}), 400

        # Create purchase record from image metadata
        purchase = PurchaseRecord(
            property_id=image.property_id,
            item_name=image.display_title or 'Unnamed Item',
            item_category=image.ai_category or 'Other',
            quantity=1,
            unit_price=image.display_price,
            total_price=image.display_price,
            vendor_name=image.display_vendor,
            purchase_status='planned',
            notes=image.ai_description or image.manual_notes
        )

        db.session.add(purchase)
        db.session.flush()

        # Link image to purchase
        image.purchase_id = purchase.purchase_id
        image.is_converted = True

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Image converted to purchase successfully',
            'purchase': purchase.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

def process_product_image_with_ai(image_data):
    """Process product image with Gemini AI to extract metadata"""
    try:
        if not GOOGLE_API_KEY or not genai:
            return None

        import base64
        from PIL import Image
        import io

        # Convert image to base64 for Gemini
        img = Image.open(io.BytesIO(image_data))

        # Resize if too large
        max_size = 1024
        if max(img.size) > max_size:
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

        # Convert to bytes
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format=img.format or 'PNG')
        img_byte_arr = img_byte_arr.getvalue()

        # Configure Gemini
        model = genai.GenerativeModel('gemini-1.5-flash')

        prompt = """Analyze this product image and extract the following information in JSON format:
{
    "title": "Product name/title (in Vietnamese if detected, otherwise English)",
    "category": "One of: Furniture, Appliances, Bedding, Kitchen, Bathroom, Decor, Electronics, Other",
    "vendor": "Store/vendor name if visible (Shopee, Lazada, etc.)",
    "price": "Price if visible (with currency)",
    "description": "Brief product description (2-3 sentences in Vietnamese)",
    "tags": "Comma-separated keywords for search (in Vietnamese)"
}

Important:
- If this is a screenshot from e-commerce site (Shopee, Lazada, etc.), extract all visible information
- Generate descriptive title even if not explicitly shown
- Infer category from product appearance
- Tags should include: product type, color, material, size keywords
- Use Vietnamese language for title, description, and tags if possible
- Return ONLY valid JSON, no other text"""

        # Call Gemini AI
        response = model.generate_content([prompt, img])

        if not response or not response.text:
            return None

        # Parse JSON response
        import json
        import re

        # Extract JSON from response
        response_text = response.text.strip()

        # Remove markdown code blocks if present
        if response_text.startswith('```'):
            response_text = re.sub(r'```json\n?|\n?```', '', response_text)

        metadata = json.loads(response_text)

        return metadata

    except Exception as e:
        print(f"❌ AI processing error: {str(e)}")
        return None

@app.route('/test_js')
def test_js():
    """Test JavaScript functions"""
    return send_from_directory('.', 'test_js_functions.html')

@app.route('/debug_functions')
def debug_functions():
    """Debug function availability"""
    return send_from_directory('.', 'debug_functions.html')

@app.route('/emergency_fix')
def emergency_fix():
    """Emergency fix for canceled customer management"""
    return send_from_directory('.', 'emergency_fix.html')

@app.route('/simple_test')
def simple_test():
    """Simple test for canceled customer management"""
    return send_from_directory('.', 'simple_test.html')


@app.route('/api/quick_notes', methods=['GET', 'POST'])
def quick_notes():
    """Quick notes management"""
    try:
        db_service = get_database_service()
        
        if request.method == 'GET':
            # Get all quick notes
            print(f"📋 [GET_QUICK_NOTES] Loading quick notes...")
            notes = db_service.get_quick_notes()
            print(f"📋 [GET_QUICK_NOTES] Found {len(notes)} notes")
            
            if notes:
                print(f"📋 [GET_QUICK_NOTES] Sample note: {notes[0]}")
                print(f"📋 [GET_QUICK_NOTES] Sample note has to_dict: {hasattr(notes[0], 'to_dict')}")
            
            # Convert to dict safely
            result = []
            for note in notes:
                try:
                    result.append(note.to_dict())
                except Exception as e:
                    print(f"❌ [QUICK_NOTES_ERROR] Error converting note {note.note_id}: {e}")
                    # Create manual dict if to_dict fails
                    result.append({
                        'note_id': note.note_id,
                        'note_type': note.note_type,
                        'content': note.note_content,
                        'completed': note.is_completed,
                        'created_at': note.created_at.isoformat() if note.created_at else None,
                        'created_by': note.created_by
                    })
            
            print(f"📋 [GET_QUICK_NOTES] Returning {len(result)} formatted notes")
            return jsonify(result)
        
        elif request.method == 'POST':
            # Create new quick note
            data = request.get_json()
            print(f"📝 [CREATE_QUICK_NOTE] Creating note: {data}")
            
            # Debug note type transformation
            original_type = data.get('type', data.get('note_type', 'general'))
            print(f"🔍 [DEBUG] Original note_type from frontend: '{original_type}'")
            print(f"🔍 [DEBUG] Type of note_type: {type(original_type)}")
            print(f"🔍 [DEBUG] Raw request data: {data}")
            
            # Validate required fields
            if not data.get('content'):
                return jsonify({'error': 'Content is required'}), 400
            
            note = db_service.create_quick_note(
                note_type=original_type,  # Use original type without transformation
                content=data.get('content', ''),
                guest_name=data.get('guest_name'),
                booking_id=data.get('booking_id'),
                priority=data.get('priority', 'normal'),
                note_date=data.get('date'),  # Pass scheduled date from frontend
                note_time=data.get('time')   # Pass scheduled time from frontend
            )
            print(f"✅ [CREATE_QUICK_NOTE] Note created successfully: {note.note_id}")
            return jsonify({
                'success': True,
                'message': 'Note created successfully',
                'note': note.to_dict()
            }), 201
    
    except Exception as e:
        print(f"❌ [QUICK_NOTES_ERROR] Error: {e}")
        import traceback
        print(f"❌ [QUICK_NOTES_ERROR] Traceback: {traceback.format_exc()}")
        return jsonify({
            'error': str(e),
            'details': 'Check server logs for more information'
        }), 500

@app.route('/api/quick_notes/<int:note_id>', methods=['GET', 'PUT', 'DELETE'])
def quick_note_detail(note_id):
    """Quick note detail operations"""
    try:
        db_service = get_database_service()
        
        if request.method == 'GET':
            note = db_service.get_quick_note(note_id)
            if not note:
                return jsonify({'error': 'Note not found'}), 404
            return jsonify(note.to_dict())
        
        elif request.method == 'PUT':
            data = request.get_json()
            print(f"✏️ [UPDATE_QUICK_NOTE] Updating note {note_id}: {data}")
            note = db_service.update_quick_note(note_id, data)
            if not note:
                return jsonify({'success': False, 'error': 'Note not found'}), 404
            print(f"✅ [UPDATE_QUICK_NOTE] Note {note_id} updated successfully")
            return jsonify({
                'success': True,
                'message': 'Note updated successfully',
                'note': note.to_dict()
            })
        
        elif request.method == 'DELETE':
            print(f"🗑️ [DELETE_QUICK_NOTE] Attempting to delete note ID: {note_id}")
            
            # ✅ ENHANCED: Check if note exists first for better debugging
            existing_note = db_service.get_quick_note(note_id)
            if not existing_note:
                print(f"❌ [DELETE_QUICK_NOTE] Note {note_id} does not exist in database")
                
                # List recent notes for debugging
                all_notes = db_service.get_quick_notes()
                print(f"🔍 [DELETE_DEBUG] Found {len(all_notes)} total notes in database")
                if all_notes:
                    recent_notes = all_notes[:5]  # Show first 5
                    print(f"🔍 [DELETE_DEBUG] Recent note IDs: {[n.note_id for n in recent_notes]}")
                
                return jsonify({
                    'success': False, 
                    'error': f'QuickNote with ID {note_id} not found',
                    'debug_info': f'Database contains {len(all_notes)} notes total'
                }), 404
            
            print(f"🗑️ [DELETE_QUICK_NOTE] Found note: '{existing_note.note_content[:50]}...'")
            success = db_service.delete_quick_note(note_id)
            if success:
                print(f"✅ [DELETE_QUICK_NOTE] Successfully deleted note {note_id}")
                return jsonify({'success': True, 'message': 'Note deleted successfully'})
            else:
                print(f"❌ [DELETE_QUICK_NOTE] Deletion failed for note {note_id}")
                return jsonify({'success': False, 'error': 'Deletion failed'}), 500
    
    except Exception as e:
        print(f"❌ [DELETE_QUICK_NOTE] Error deleting note {note_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/arrival_times', methods=['GET', 'POST'])
def arrival_times():
    """Arrival times management"""
    try:
        db_service = get_database_service()
        
        if request.method == 'GET':
            # Get all arrival times
            arrival_times = db_service.get_arrival_times()
            return jsonify([at.to_dict() for at in arrival_times])
        
        elif request.method == 'POST':
            # Create or update arrival time
            data = request.get_json()
            print(f"🕐 [ARRIVAL_TIME] Received data: {data}")
            
            booking_id = data.get('booking_id')
            estimated_arrival = data.get('estimated_arrival')
            notes = data.get('notes', '')
            
            if not booking_id:
                return jsonify({'success': False, 'error': 'booking_id is required'}), 400
            
            try:
                arrival_time = db_service.upsert_arrival_time(
                    booking_id=booking_id,
                    estimated_arrival=estimated_arrival,
                    notes=notes
                )
                print(f"🕐 [ARRIVAL_TIME] Successfully saved: booking_id={booking_id}, time={estimated_arrival}")
                return jsonify({'success': True, 'data': arrival_time.to_dict()})
            
            except Exception as e:
                print(f"🕐 [ARRIVAL_TIME] Error saving: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/arrival_times/<booking_id>', methods=['DELETE'])
def delete_arrival_time(booking_id):
    """Clear late-arrival record for a booking."""
    try:
        from core.models import db as _atdb, ArrivalTime as _AT
        _AT.query.filter_by(booking_id=booking_id).delete()
        _atdb.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        try:
            from core.models import db as _atdb2
            _atdb2.session.rollback()
        except Exception:
            pass
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/analyze_duplicates', methods=['GET'])
def analyze_duplicates_api():
    """API endpoint for AI duplicate analysis with timeout and better error handling"""
    import time
    start_time = time.time()
    
    print("🤖 [API] Analyze duplicates endpoint called")
    
    try:
        # Load data with timeout protection
        print("🤖 [API] Loading booking data...")
        df, _ = load_data()
        load_time = time.time() - start_time
        print(f"🤖 [API] Data loaded in {load_time:.2f}s, shape: {df.shape}")
        
        if df.empty:
            print("🤖 [API] No booking data found")
            return jsonify({
                'success': True,
                'data': {
                    'duplicate_groups': [],
                    'total_duplicates': 0,
                    'message': 'No booking data found'
                }
            })
        
        # Use the existing duplicate analysis function with timeout
        print("🤖 [API] Starting duplicate analysis...")
        analysis_result = analyze_existing_duplicates(df)
        
        total_time = time.time() - start_time
        print(f"🤖 [API] Analysis completed in {total_time:.2f}s")
        
        # Ensure we have the expected structure
        if 'total_duplicates' not in analysis_result:
            analysis_result['total_duplicates'] = len(analysis_result.get('duplicate_groups', []))
        
        return jsonify({
            'success': True,
            'data': analysis_result,
            'message': f'Found {analysis_result["total_duplicates"]} duplicate groups',
            'processing_time': total_time
        })
        
    except Exception as e:
        error_time = time.time() - start_time
        print(f"🤖 [API] Error in duplicate analysis after {error_time:.2f}s: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            'success': False,
            'message': f'Server error: {str(e)}',
            'processing_time': error_time,
            'error_type': type(e).__name__
        }), 500


@app.route('/api/test_gemini', methods=['GET'])
def test_gemini_api():
    """Test endpoint to verify Gemini API connectivity"""
    try:
        if not GOOGLE_API_KEY or GOOGLE_API_KEY == 'your_gemini_api_key':
            return jsonify({
                'success': False,
                'message': 'Gemini API key not configured'
            }), 400
        
        # Test simple generation
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content("Respond with exactly: API Working")
        
        if response and response.text:
            return jsonify({
                'success': True,
                'message': 'Gemini API working correctly',
                'response': response.text.strip()
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Gemini API returned empty response'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Gemini API error: {str(e)}'
        }), 500

@app.route('/api/hidden_guests_for_date', methods=['GET'])
def hidden_guests_for_date():
    """Query DB directly for bookings touching the given date that are hidden (no arrival confirmation)."""
    try:
        from core.models import db as _db
        date_str = request.args.get('date', '')
        if not date_str:
            return jsonify({'guests': []})
        try:
            target = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'guests': [], 'error': 'Invalid date'}), 400

        vn_today = (datetime.utcnow() + timedelta(hours=7)).date()
        rows = _db.session.execute(text("""
            SELECT booking_id, guest_name, accommodation_name,
                   checkin_date, checkout_date, room_amount,
                   checkin_status, arrival_confirmed, booking_status
            FROM bookings
            WHERE (booking_status IS NULL OR booking_status NOT IN ('cancelled','deleted','huy','xoa'))
              AND (
                -- Case 1: check-in BEFORE today, unconfirmed → truly missed (hidden by no-show filter)
                (DATE(checkin_date) = :d AND :d < :today
                 AND (checkin_status IS NULL OR checkin_status = '')
                 AND (arrival_confirmed IS NULL OR arrival_confirmed IS FALSE))
                OR
                -- Case 2: explicitly marked no_show or cancelling (touches the date range)
                (DATE(checkin_date) <= :d AND DATE(checkout_date) > :d
                 AND checkin_status IN ('no_show', 'cancelling'))
                OR
                -- Case 3: viewing a future date — arrival day already came but not confirmed yet,
                -- so they're left out of that day's staying / check-out lists
                (:d > :today
                 AND DATE(checkin_date) <= :today AND DATE(checkin_date) >= :grace_start
                 AND DATE(checkout_date) >= :d
                 AND (checkin_status IS NULL OR checkin_status = '')
                 AND (arrival_confirmed IS NULL OR arrival_confirmed IS FALSE))
              )
        """), {'d': target, 'today': vn_today, 'grace_start': vn_today - timedelta(days=2)}).fetchall()

        guests = []
        for r in rows:
            st = r[6] or ''
            ac = r[7]
            label = 'Không đến' if st == 'no_show' else ('Huỷ' if st == 'cancelling' else 'Chưa xác nhận')
            try:
                ci = r[3].strftime('%d/%m') if r[3] else ''
                co = r[4].strftime('%d/%m') if r[4] else ''
            except Exception:
                ci = co = ''
            guests.append({
                'bid':         str(r[0]),
                'name':        r[1] or 'N/A',
                'room':        r[2] or '',
                'ci':          ci,
                'co':          co,
                'amount':      float(r[5] or 0),
                'status_label': label,
            })
        return jsonify({'guests': guests})
    except Exception as e:
        return jsonify({'guests': [], 'error': str(e)}), 500


@app.route('/api/restore_arrival', methods=['POST'])
def restore_arrival():
    """Restore a hidden guest: set checkin_status='confirmed' + arrival_confirmed=True"""
    try:
        from core.models import Booking as _BM, db as _db
        data = request.get_json() or {}
        booking_id = data.get('booking_id')
        if not booking_id:
            return jsonify({'success': False, 'message': 'Thiếu booking_id'}), 400
        booking = _BM.query.get(booking_id)
        if not booking:
            return jsonify({'success': False, 'message': 'Không tìm thấy booking'}), 404
        booking.checkin_status = 'confirmed'
        booking.arrival_confirmed = True
        booking.arrival_confirmed_at = datetime.now()
        _db.session.commit()
        print(f"[RESTORE_ARRIVAL] Booking {booking_id} restored to confirmed")
        return jsonify({'success': True, 'message': 'Đã khôi phục xác nhận đến'})
    except Exception as e:
        try:
            from core.models import db as _db2; _db2.session.rollback()
        except Exception:
            pass
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/mark_no_show', methods=['POST'])
def mark_no_show():
    """Mark a booking as no-show — sets checkin_status='no_show' so it stops appearing in overdue panel"""
    try:
        from core.models import Booking as _BM, db as _db
        data = request.get_json() or {}
        booking_id = data.get('booking_id')
        if not booking_id:
            return jsonify({'success': False, 'message': 'Thiếu booking_id'}), 400
        booking = _BM.query.get(booking_id)
        if not booking:
            return jsonify({'success': False, 'message': 'Không tìm thấy booking'}), 404
        booking.checkin_status = 'no_show'
        booking.arrival_confirmed = False
        _db.session.commit()
        print(f"[MARK_NO_SHOW] Booking {booking_id} marked as no_show")
        return jsonify({'success': True, 'message': 'Đã đánh dấu không đến'})
    except Exception as e:
        try:
            from core.models import db as _db2; _db2.session.rollback()
        except Exception:
            pass
        return jsonify({'success': False, 'message': str(e)}), 500


