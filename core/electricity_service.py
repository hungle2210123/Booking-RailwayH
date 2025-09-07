"""
Electricity Management Service
Handle CRUD operations for electricity meters, readings, images, and bills
"""

import os
import base64
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Any
from sqlalchemy.exc import IntegrityError
from sqlalchemy import desc, asc, and_, or_, func

from .models import (
    db, ElectricityMeter, ElectricityReading, 
    ElectricityImage, ElectricityBill
)


class ElectricityService:
    """Service class for electricity management operations"""
    
    # =====================================================
    # METER MANAGEMENT
    # =====================================================
    
    @staticmethod
    def create_meter(meter_id: str, location: str, brand: str = None, model: str = None, notes: str = None) -> Dict[str, Any]:
        """Create a new electricity meter"""
        try:
            # Check if meter already exists
            existing_meter = ElectricityMeter.query.filter_by(meter_id=meter_id).first()
            if existing_meter:
                return {'success': False, 'error': f'Meter with ID {meter_id} already exists'}
            
            meter = ElectricityMeter(
                meter_id=meter_id,
                location=location,
                brand=brand,
                model=model,
                notes=notes
            )
            
            db.session.add(meter)
            db.session.commit()
            
            return {'success': True, 'data': meter.to_dict()}
            
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def get_all_meters(active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all electricity meters"""
        query = ElectricityMeter.query
        if active_only:
            query = query.filter_by(is_active=True)
        
        meters = query.order_by(ElectricityMeter.location).all()
        return [meter.to_dict() for meter in meters]
    
    @staticmethod
    def get_meter_by_id(meter_id: str) -> Optional[Dict[str, Any]]:
        """Get meter by meter_id"""
        meter = ElectricityMeter.query.filter_by(meter_id=meter_id).first()
        return meter.to_dict() if meter else None
    
    @staticmethod
    def update_meter(meter_uuid: int, **kwargs) -> Dict[str, Any]:
        """Update meter information"""
        try:
            meter = ElectricityMeter.query.get(meter_uuid)
            if not meter:
                return {'success': False, 'error': 'Meter not found'}
            
            for key, value in kwargs.items():
                if hasattr(meter, key):
                    setattr(meter, key, value)
            
            db.session.commit()
            return {'success': True, 'data': meter.to_dict()}
            
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def delete_meter(meter_uuid: int) -> Dict[str, Any]:
        """Soft delete meter (set inactive)"""
        try:
            meter = ElectricityMeter.query.get(meter_uuid)
            if not meter:
                return {'success': False, 'error': 'Meter not found'}
            
            meter.is_active = False
            db.session.commit()
            
            return {'success': True, 'message': 'Meter deactivated successfully'}
            
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    # =====================================================
    # READING MANAGEMENT
    # =====================================================
    
    @staticmethod
    def create_reading(meter_id: str, kwh_reading: float, electricity_price: float, 
                      reading_date: date = None, notes: str = None) -> Dict[str, Any]:
        """Create a new electricity reading"""
        try:
            # Get meter
            meter = ElectricityMeter.query.filter_by(meter_id=meter_id).first()
            if not meter:
                return {'success': False, 'error': f'Meter with ID {meter_id} not found'}
            
            if reading_date is None:
                reading_date = date.today()
            
            # Get previous reading for consumption calculation
            previous_reading = ElectricityReading.query.filter_by(
                meter_uuid=meter.meter_uuid
            ).order_by(desc(ElectricityReading.reading_date)).first()
            
            consumption = None
            amount = None
            previous_reading_id = None
            
            if previous_reading and kwh_reading >= previous_reading.kwh_reading:
                consumption = kwh_reading - previous_reading.kwh_reading
                amount = consumption * electricity_price
                previous_reading_id = previous_reading.reading_id
            
            reading = ElectricityReading(
                meter_uuid=meter.meter_uuid,
                reading_date=reading_date,
                kwh_reading=kwh_reading,
                electricity_price=electricity_price,
                consumption=consumption,
                amount=amount,
                previous_reading_id=previous_reading_id,
                notes=notes
            )
            
            db.session.add(reading)
            db.session.commit()
            
            return {'success': True, 'data': reading.to_dict()}
            
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def get_readings(meter_id: str = None, start_date: date = None, end_date: date = None, 
                    limit: int = 100) -> List[Dict[str, Any]]:
        """Get electricity readings with optional filters"""
        query = ElectricityReading.query.join(ElectricityMeter)
        
        if meter_id:
            query = query.filter(ElectricityMeter.meter_id == meter_id)
        
        if start_date:
            query = query.filter(ElectricityReading.reading_date >= start_date)
        
        if end_date:
            query = query.filter(ElectricityReading.reading_date <= end_date)
        
        readings = query.order_by(desc(ElectricityReading.reading_date)).limit(limit).all()
        return [reading.to_dict() for reading in readings]
    
    @staticmethod
    def update_reading(reading_id: int, **kwargs) -> Dict[str, Any]:
        """Update reading information"""
        try:
            reading = ElectricityReading.query.get(reading_id)
            if not reading:
                return {'success': False, 'error': 'Reading not found'}
            
            for key, value in kwargs.items():
                if hasattr(reading, key):
                    setattr(reading, key, value)
            
            # Recalculate consumption and amount if relevant fields changed
            if 'kwh_reading' in kwargs or 'electricity_price' in kwargs:
                previous_reading = ElectricityReading.query.filter(
                    and_(
                        ElectricityReading.meter_uuid == reading.meter_uuid,
                        ElectricityReading.reading_date < reading.reading_date
                    )
                ).order_by(desc(ElectricityReading.reading_date)).first()
                
                if previous_reading and reading.kwh_reading >= previous_reading.kwh_reading:
                    reading.consumption = reading.kwh_reading - previous_reading.kwh_reading
                    reading.amount = reading.consumption * reading.electricity_price
                    reading.previous_reading_id = previous_reading.reading_id
            
            db.session.commit()
            return {'success': True, 'data': reading.to_dict()}
            
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def delete_reading(reading_id: int) -> Dict[str, Any]:
        """Delete a reading and its associated images"""
        try:
            reading = ElectricityReading.query.get(reading_id)
            if not reading:
                return {'success': False, 'error': 'Reading not found'}
            
            db.session.delete(reading)
            db.session.commit()
            
            return {'success': True, 'message': 'Reading deleted successfully'}
            
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    # =====================================================
    # IMAGE MANAGEMENT
    # =====================================================
    
    @staticmethod
    def save_image(reading_id: int, image_data: str, image_filename: str, 
                  image_type: str = 'meter_reading', description: str = None) -> Dict[str, Any]:
        """Save image data for a reading"""
        try:
            reading = ElectricityReading.query.get(reading_id)
            if not reading:
                return {'success': False, 'error': 'Reading not found'}
            
            # Extract image format from filename
            image_format = image_filename.split('.')[-1].lower() if '.' in image_filename else 'jpg'
            
            # Calculate approximate file size (base64 is ~33% larger than original)
            file_size = int(len(image_data) * 0.75) if image_data else 0
            
            image = ElectricityImage(
                reading_id=reading_id,
                image_filename=image_filename,
                image_type=image_type,
                image_data=image_data,
                file_size=file_size,
                image_format=image_format,
                description=description
            )
            
            db.session.add(image)
            db.session.commit()
            
            return {'success': True, 'data': image.to_dict()}
            
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def get_images(reading_id: int) -> List[Dict[str, Any]]:
        """Get all images for a reading"""
        images = ElectricityImage.query.filter_by(reading_id=reading_id).all()
        return [image.to_dict() for image in images]
    
    @staticmethod
    def get_image_data(image_id: int) -> Optional[str]:
        """Get base64 image data"""
        image = ElectricityImage.query.get(image_id)
        return image.image_data if image else None
    
    @staticmethod
    def delete_image(image_id: int) -> Dict[str, Any]:
        """Delete an image"""
        try:
            image = ElectricityImage.query.get(image_id)
            if not image:
                return {'success': False, 'error': 'Image not found'}
            
            db.session.delete(image)
            db.session.commit()
            
            return {'success': True, 'message': 'Image deleted successfully'}
            
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    # =====================================================
    # BILL MANAGEMENT
    # =====================================================
    
    @staticmethod
    def create_bill_from_readings(start_date: date, end_date: date, notes: str = None) -> Dict[str, Any]:
        """Create a bill from readings within a date range"""
        try:
            # Get all readings in the period
            readings = ElectricityReading.query.filter(
                and_(
                    ElectricityReading.reading_date >= start_date,
                    ElectricityReading.reading_date <= end_date,
                    ElectricityReading.consumption.isnot(None)
                )
            ).all()
            
            if not readings:
                return {'success': False, 'error': 'No readings found in the specified period'}
            
            # Calculate bill totals
            total_meters = len(set(reading.meter_uuid for reading in readings))
            total_consumption = sum(float(reading.consumption) for reading in readings if reading.consumption)
            total_amount = sum(float(reading.amount) for reading in readings if reading.amount)
            
            # Calculate average price
            total_kwh = sum(float(reading.consumption) for reading in readings if reading.consumption)
            average_price = total_amount / total_kwh if total_kwh > 0 else 0
            
            bill = ElectricityBill(
                bill_date=date.today(),
                bill_period_start=start_date,
                bill_period_end=end_date,
                total_meters=total_meters,
                total_consumption=total_consumption,
                average_price=average_price,
                total_amount=total_amount,
                notes=notes
            )
            
            db.session.add(bill)
            db.session.commit()
            
            return {'success': True, 'data': bill.to_dict()}
            
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def get_bills(limit: int = 50) -> List[Dict[str, Any]]:
        """Get all bills ordered by date"""
        bills = ElectricityBill.query.order_by(desc(ElectricityBill.bill_date)).limit(limit).all()
        return [bill.to_dict() for bill in bills]
    
    @staticmethod
    def update_bill(bill_id: int, **kwargs) -> Dict[str, Any]:
        """Update bill information"""
        try:
            bill = ElectricityBill.query.get(bill_id)
            if not bill:
                return {'success': False, 'error': 'Bill not found'}
            
            for key, value in kwargs.items():
                if hasattr(bill, key):
                    setattr(bill, key, value)
            
            db.session.commit()
            return {'success': True, 'data': bill.to_dict()}
            
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    # =====================================================
    # UTILITY FUNCTIONS
    # =====================================================
    
    @staticmethod
    def get_dashboard_stats() -> Dict[str, Any]:
        """Get dashboard statistics for electricity management"""
        try:
            total_meters = ElectricityMeter.query.filter_by(is_active=True).count()
            total_readings = ElectricityReading.query.count()
            
            # Current month consumption
            current_month_start = date.today().replace(day=1)
            current_month_readings = ElectricityReading.query.filter(
                and_(
                    ElectricityReading.reading_date >= current_month_start,
                    ElectricityReading.consumption.isnot(None)
                )
            ).all()
            
            current_month_consumption = sum(
                float(reading.consumption) for reading in current_month_readings 
                if reading.consumption
            )
            
            current_month_amount = sum(
                float(reading.amount) for reading in current_month_readings 
                if reading.amount
            )
            
            # Last reading date
            last_reading = ElectricityReading.query.order_by(
                desc(ElectricityReading.reading_date)
            ).first()
            
            return {
                'success': True,
                'data': {
                    'total_meters': total_meters,
                    'total_readings': total_readings,
                    'current_month_consumption': current_month_consumption,
                    'current_month_amount': current_month_amount,
                    'last_reading_date': last_reading.reading_date.isoformat() if last_reading else None
                }
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def search_data(query: str, search_type: str = 'all') -> Dict[str, Any]:
        """Search across meters, readings, and bills"""
        try:
            results = {}
            
            if search_type in ['all', 'meters']:
                meters = ElectricityMeter.query.filter(
                    or_(
                        ElectricityMeter.meter_id.ilike(f'%{query}%'),
                        ElectricityMeter.location.ilike(f'%{query}%'),
                        ElectricityMeter.brand.ilike(f'%{query}%'),
                        ElectricityMeter.model.ilike(f'%{query}%')
                    )
                ).all()
                results['meters'] = [meter.to_dict() for meter in meters]
            
            if search_type in ['all', 'readings']:
                # Search readings by meter info or notes
                readings = ElectricityReading.query.join(ElectricityMeter).filter(
                    or_(
                        ElectricityMeter.meter_id.ilike(f'%{query}%'),
                        ElectricityMeter.location.ilike(f'%{query}%'),
                        ElectricityReading.notes.ilike(f'%{query}%')
                    )
                ).order_by(desc(ElectricityReading.reading_date)).limit(50).all()
                results['readings'] = [reading.to_dict() for reading in readings]
            
            return {'success': True, 'data': results}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}