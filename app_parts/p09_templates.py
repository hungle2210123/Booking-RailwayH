# p09_templates — message templates API (Mẫu Câu) + template images, canceled bookings restore/delete
# Part of app.py (lines 11164-12225 before the Oct 25 split). Runs inside app.py's namespace
# (see the loader at the end of app.py): every name defined in app.py and earlier parts is available here.
@app.route('/api/templates', methods=['GET'])
def get_templates():
    """Get all message templates from PostgreSQL database"""
    try:
        # Import the MessageTemplate model
        from core.models import MessageTemplate, db
        
        # Test raw SQL query first to debug columns issue
        try:
            raw_result = db.session.execute(text("SELECT template_id, template_name, category, template_content FROM message_templates LIMIT 1")).fetchall()
            print(f"🔍 Raw SQL works: {len(raw_result)} rows")
        except Exception as raw_error:
            print(f"❌ Raw SQL error: {raw_error}")
            # Fallback to table existence check
            tables_result = db.session.execute(text("SELECT table_name FROM information_schema.tables WHERE table_name='message_templates'")).fetchall()
            print(f"🔍 Table exists check: {tables_result}")
        
        # Query all templates from database ordered by category and name
        templates_query = MessageTemplate.query.order_by(MessageTemplate.category, MessageTemplate.template_name).all()
        
        print(f"📋 Templates API: Querying database...")
        print(f"📋 Templates API: Found {len(templates_query)} templates in database")
        
        # Debug: Check what's actually in the database
        if templates_query:
            sample = templates_query[0]
            print(f"📋 Sample template - ID: {sample.template_id}, Name: {sample.template_name}, Category: {sample.category}")
        
        # Convert to format expected by JavaScript with improved titles
        templates_data = []
        for template in templates_query:
            # Get raw category from database
            raw_category = template.category or 'General'
            print(f"📋 Processing template: {template.template_name}, Raw Category: '{raw_category}'")
            
            # Improve category names for better display
            category = raw_category
            if category == 'DON PHONG':
                category = 'Room Cleaning'
            elif category == 'HET PHONG':
                category = 'Room Unavailable'
            elif category == 'NOT BOOKING':
                category = 'Direct Booking'
            elif category == 'FEED BACK':
                category = 'Feedback & Farewell'
            elif category == 'EARLY CHECK IN':
                category = 'Early Check-in'
            elif category == 'CHECK IN':
                category = 'Check-in Instructions'
            
            # Use template_name as label (it should already be improved from import)
            label = template.template_name or 'Unnamed Template'
            
            # Generate image URLs for multiple images
            images = []
            legacy_image_url = None
            
            # Check for new multi-image system
            if hasattr(template, 'images') and template.images:
                for img in sorted(template.images, key=lambda x: x.image_order):
                    image_filename = os.path.basename(img.image_path)
                    images.append({
                        'id': img.image_id,
                        'url': f'/api/templates/image/{image_filename}',
                        'filename': img.image_filename,
                        'order': img.image_order,
                        'alt_text': img.alt_text
                    })
            
            # Legacy single image support
            if template.image_path:
                image_filename = os.path.basename(template.image_path)
                legacy_image_url = f'/api/templates/image/{image_filename}'
                
                # If no multi-images, create from legacy
                if not images:
                    images.append({
                        'id': None,
                        'url': legacy_image_url,
                        'filename': image_filename,
                        'order': 1,
                        'alt_text': None
                    })
            
            templates_data.append({
                'Category': category,
                'Label': label,
                'Message': template.template_content,
                # Frontend expects these lowercase fields
                'category': category,
                'label': label, 
                'content': template.template_content,
                'id': template.template_id,
                'image_path': template.image_path,
                'image_url': legacy_image_url,  # Keep for backward compatibility
                'images': images,  # New multi-image support
                'created_at': template.created_at.isoformat() if template.created_at else None
            })
        
        print(f"📋 Templates API: Processed {len(templates_data)} templates")
        
        # Debug: Show sample template structure
        if templates_data:
            sample = templates_data[0]
            print(f"📋 Sample template structure:")
            print(f"   - label: '{sample.get('label', 'MISSING')}'")
            print(f"   - content length: {len(sample.get('content', ''))}")
            print(f"   - id: {sample.get('id', 'MISSING')}")
        
        # Group by category for better organization
        from collections import defaultdict
        categories_dict = defaultdict(list)
        for template in templates_data:
            categories_dict[template['Category']].append(template)
        
        print(f"📋 Templates API: Organized into {len(categories_dict)} categories: {list(categories_dict.keys())}")
        
        # Return in format expected by JavaScript
        return jsonify({
            'success': True,
            'templates': templates_data
        })
    except Exception as e:
        print(f"Error getting templates: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/templates/add', methods=['POST'])
def add_template():
    """Add a new message template to PostgreSQL database"""
    try:
        from core.models import MessageTemplate, db
        
        data = request.get_json()
        print(f"🔍 [TEMPLATE_ADD] Received data: {data}")
        
        # Enhanced validation with better debugging
        if not data:
            print("❌ [TEMPLATE_ADD] No data received")
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        # Check for multiple possible field names
        name = data.get('name') or data.get('template_name') or data.get('Label')
        content = data.get('content') or data.get('template_content') or data.get('Message')
        category = data.get('category') or data.get('Category') or 'General'
        
        if not name or not content:
            print(f"❌ [TEMPLATE_ADD] Missing fields - name: {name}, content: {content}")
            return jsonify({'success': False, 'error': 'Name and content are required'}), 400
        
        # Fix sequence if needed (check if sequence is behind the actual data)
        try:
            # Get the current max ID in the table
            max_id = db.session.query(db.func.max(MessageTemplate.template_id)).scalar() or 0
            
            # Get the current sequence value without advancing it
            sequence_val = db.session.execute(db.text("SELECT last_value FROM message_templates_template_id_seq")).scalar()
            
            print(f"🔍 [TEMPLATE_ADD] Sequence check: max_id={max_id}, sequence_val={sequence_val}")
            
            # If sequence is behind, reset it
            if sequence_val <= max_id:
                reset_val = max_id + 1
                db.session.execute(db.text(f"SELECT setval('message_templates_template_id_seq', {reset_val})"))
                db.session.commit()
                print(f"🔧 [TEMPLATE_ADD] Fixed sequence: set to {reset_val} (was {sequence_val}, max_id was {max_id})")
        except Exception as seq_error:
            print(f"⚠️ [TEMPLATE_ADD] Sequence fix error: {seq_error}")
            # Try a simpler approach - just reset to max+1
            try:
                max_id = db.session.query(db.func.max(MessageTemplate.template_id)).scalar() or 0
                reset_val = max_id + 1
                db.session.execute(db.text(f"SELECT setval('message_templates_template_id_seq', {reset_val})"))
                db.session.commit()
                print(f"🔧 [TEMPLATE_ADD] Fallback sequence fix: set to {reset_val}")
            except Exception as fallback_error:
                print(f"❌ [TEMPLATE_ADD] Fallback sequence fix failed: {fallback_error}")
        
        # Create new template in database
        new_template = MessageTemplate(
            template_name=name,
            category=category,
            template_content=content
        )
        
        # Save to database
        db.session.add(new_template)
        db.session.commit()
        
        print(f"📋 Templates API: Added new template '{name}' with ID {new_template.template_id}")
        print(f"📋 Templates API: Mapped fields - name: {name}, category: {category}, content: {content[:50]}...")
        
        # Return the added template in the correct format
        response = {
            'success': True,
            'message': 'Template added successfully',
            'template': {
                'Category': new_template.category,
                'Label': new_template.template_name,
                'Message': new_template.template_content,
                'id': new_template.template_id,
                'created_at': new_template.created_at.isoformat() if new_template.created_at else None
            }
        }
        return jsonify(response)
    except Exception as e:
        print(f"Error adding template: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/templates/<template_id>', methods=['GET', 'PUT', 'DELETE'])
def handle_template(template_id):
    """Get, update or delete a specific template from PostgreSQL database"""
    try:
        from core.models import MessageTemplate, db
        
        # Find template by ID
        template = MessageTemplate.query.get(template_id)
        if not template:
            return jsonify({'success': False, 'error': 'Template not found'}), 404
        
        if request.method == 'GET':
            # Return template details in the correct format
            return jsonify({
                'success': True,
                'template': {
                    'Category': template.category or 'General',
                    'Label': template.template_name,
                    'Message': template.template_content,
                    'id': template.template_id,
                    'created_at': template.created_at.isoformat() if template.created_at else None
                }
            })
        
        elif request.method == 'PUT':
            # Update template with new data
            data = request.get_json()
            print(f"🔍 [TEMPLATE_UPDATE] Received data: {data}")
            if not data:
                return jsonify({'success': False, 'error': 'No data provided'}), 400
            
            # Track if name is being updated for validation
            new_name = None
            if 'template_name' in data or 'name' in data or 'Label' in data:
                new_name = data.get('template_name') or data.get('name') or data.get('Label')
                
                # Validate unique name if it's being changed
                if new_name and new_name != template.template_name:
                    existing_template = MessageTemplate.query.filter(
                        MessageTemplate.template_name == new_name,
                        MessageTemplate.template_id != template_id
                    ).first()
                    
                    if existing_template:
                        print(f"❌ [TEMPLATE_UPDATE] Name '{new_name}' already exists for template ID {existing_template.template_id}")
                        return jsonify({
                            'success': False, 
                            'error': f'Template name "{new_name}" already exists. Please choose a different name.'
                        }), 400
                
                template.template_name = new_name
            
            # Update other template fields with multiple field name support
            if 'category' in data or 'Category' in data:
                template.category = data.get('category') or data.get('Category')
            if 'template_content' in data or 'content' in data or 'Message' in data:
                template.template_content = data.get('template_content') or data.get('content') or data.get('Message')
            
            # Save to database
            db.session.commit()
            
            print(f"📋 Templates API: Updated template '{template.template_name}' (ID: {template_id})")
            print(f"📋 Templates API: Update fields applied - category: {template.category}, name: {template.template_name}, content: {template.template_content[:50]}...")
            
            return jsonify({
                'success': True,
                'message': f'Template {template_id} updated successfully',
                'template': {
                    'Category': template.category or 'General',
                    'Label': template.template_name,
                    'Message': template.template_content,
                    'id': template.template_id
                }
            })
        
        elif request.method == 'DELETE':
            # Delete template from database
            db.session.delete(template)
            db.session.commit()
            
            print(f"📋 Templates API: Deleted template '{template.template_name}' (ID: {template_id})")
            
            return jsonify({
                'success': True,
                'message': f'Template {template_id} deleted successfully'
            })
    except Exception as e:
        print(f"Error handling template {template_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/templates/image/<filename>')
def serve_template_image(filename):
    """Serve template images"""
    try:
        # Try multiple possible directories
        possible_dirs = [
            os.path.join('static', 'images', 'templates'),
            os.path.join('static', 'template_images'),
            os.path.join('static', 'images'),
            'static'
        ]
        
        for template_images_dir in possible_dirs:
            full_path = os.path.join(template_images_dir, filename)
            if os.path.exists(full_path):
                print(f"📋 Serving image from: {full_path}")
                return send_from_directory(template_images_dir, filename)
        
        # Pictures added from "⚙️ Tin & ảnh" are stored in the database (Railway's disk is wiped on deploy)
        from core.models import db as _xdb
        from core import journey as _J
        _J.ensure(_xdb.session)
        row = _xdb.session.execute(text(
            "SELECT image_data, image_mime FROM template_images WHERE image_filename = :f AND image_data IS NOT NULL"),
            {'f': filename}).fetchone()
        if row:
            resp = app.response_class(bytes(row[0]), mimetype=row[1] or 'image/jpeg')
            resp.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
            return resp

        print(f"❌ Image not found: {filename}")
        return jsonify({'error': 'Image not found'}), 404
        
    except Exception as e:
        print(f"Error serving template image: {e}")
        return jsonify({'error': 'Image not found'}), 404

@app.route('/api/templates/<template_id>/images', methods=['GET'])
def get_template_images(template_id):
    """Get all images for a template"""
    try:
        from core.models import MessageTemplate, TemplateImage
        
        # Find the template
        template = MessageTemplate.query.get(template_id)
        if not template:
            return jsonify({'success': False, 'error': 'Template not found'}), 404
        
        # Get all images for this template (with fallback if table doesn't exist)
        images = []
        try:
            if template.images:
                for img in template.images:
                    images.append({
                        'id': img.image_id,
                        'filename': img.image_filename,
                        'url': f'/api/templates/image/{img.image_filename}',
                        'alt_text': img.alt_text,
                        'order': img.image_order
                    })
        except Exception as e:
            print(f"Warning: Could not load template images, table might not exist: {e}")
            # Return empty images array if table doesn't exist
        
        # Sort by order
        images.sort(key=lambda x: x['order'])
        
        return jsonify({
            'success': True,
            'images': images,
            'count': len(images)
        })
        
    except Exception as e:
        print(f"Error getting template images: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/templates/<template_id>/images', methods=['POST'])
def add_template_images(template_id):
    """Add a single image to a template"""
    try:
        from core.models import MessageTemplate, TemplateImage, db
        
        # Find the template
        template = MessageTemplate.query.get(template_id)
        if not template:
            return jsonify({'success': False, 'error': 'Template not found'}), 404
        
        # Check how many images the template already has (with fallback if table doesn't exist)
        try:
            current_image_count = len(template.images) if template.images else 0
        except Exception as e:
            print(f"Warning: template_images table might not exist: {e}")
            current_image_count = 0
        
        # Get uploaded file (single image)
        if 'image' not in request.files:
            return jsonify({'success': False, 'error': 'No image file provided'}), 400
        
        file = request.files['image']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No image selected'}), 400
        
        # Limit to 3 images total
        max_images = 3
        if current_image_count >= max_images:
            return jsonify({
                'success': False, 
                'error': f'Maximum {max_images} images allowed per template. Currently have {current_image_count}.'
            }), 400
        
        # Check file extension
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
        if not ('.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in allowed_extensions):
            return jsonify({'success': False, 'error': 'Invalid file type. Allowed: PNG, JPG, JPEG, GIF, WEBP'}), 400
        
        # Generate secure filename
        filename = secure_filename(file.filename)
        timestamp = int(time.time())
        name, ext = os.path.splitext(filename)
        unique_filename = f"template_{template_id}_{timestamp}_{name}{ext}"
        
        # Save file
        upload_path = os.path.join('static', 'images', 'templates', unique_filename)
        full_path = os.path.join(os.getcwd(), upload_path)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        image_bytes = file.read()
        file.stream.seek(0)
        file.save(full_path)
        if not image_bytes or len(image_bytes) > 8 * 1024 * 1024:
            return jsonify({'success': False, 'error': 'Ảnh rỗng hoặc lớn hơn 8MB'}), 400
        
        # Create database record (with error handling for missing table)
        try:
            template_image = TemplateImage(
                template_id=template_id,
                image_path=upload_path,
                image_filename=unique_filename,
                image_order=current_image_count + 1
            )
            
            db.session.add(template_image)
            db.session.flush()
            # The picture itself lives in the database: files on Railway's disk vanish at every deploy
            # (IMG_3831 added to 3 payment templates on Oct 18 was lost that way)
            from core import journey as _J
            _J.ensure(db.session)
            db.session.execute(text("UPDATE template_images SET image_data = :d, image_mime = :m WHERE image_id = :i"),
                               {'d': image_bytes, 'm': (file.mimetype or 'image/jpeg')[:30], 'i': template_image.image_id})
            db.session.commit()
            
            print(f"📋 Template Images: Added image to template {template_id}")
            
            return jsonify({
                'success': True,
                'message': 'Successfully added image',
                'image': {
                    'id': template_image.image_id,
                    'filename': unique_filename,
                    'url': f'/api/templates/image/{unique_filename}',
                    'order': current_image_count + 1
                }
            })
            
        except Exception as db_error:
            # If database operation fails, clean up the file
            try:
                if os.path.exists(full_path):
                    os.remove(full_path)
            except:
                pass
                
            if 'template_images' in str(db_error).lower():
                return jsonify({
                    'success': False, 
                    'error': 'Database not ready. Please run database migration first.',
                    'migration_needed': True
                }), 400
            else:
                raise db_error
        
    except Exception as e:
        print(f"Error adding template images: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/templates/<template_id>/legacy-image', methods=['DELETE'])
def delete_legacy_image(template_id):
    """Delete legacy image from message_templates.image_path"""
    try:
        from core.models import MessageTemplate, db
        
        # Find the template
        template = MessageTemplate.query.get(template_id)
        if not template:
            return jsonify({'success': False, 'error': 'Template not found'}), 404
        
        if not template.image_path:
            return jsonify({'success': False, 'error': 'No legacy image found'}), 404
        
        # Delete file from filesystem
        try:
            full_path = os.path.join(os.getcwd(), template.image_path)
            if os.path.exists(full_path):
                os.remove(full_path)
                print(f"📋 Deleted legacy image file: {full_path}")
        except Exception as e:
            print(f"Warning: Could not delete legacy image file {template.image_path}: {e}")
        
        # Clear the image_path column
        template.image_path = None
        db.session.commit()
        
        print(f"📋 Legacy image deleted for template {template_id}")
        
        return jsonify({
            'success': True,
            'message': 'Legacy image deleted successfully'
        })
        
    except Exception as e:
        print(f"Error deleting legacy image: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


