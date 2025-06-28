"""
Data Synchronization Service
Handles automatic data import/sync functionality for Railway app
"""

import os
import psycopg2
import pandas as pd
import numpy as np
from datetime import datetime
from flask import current_app

class DataSyncService:
    """Service for synchronizing data between local and Railway databases"""
    
    def __init__(self):
        self.local_db_url = os.getenv('LOCAL_DATABASE_URL', 'postgresql://postgres:locloc123@localhost:5432/hotel_booking')
        self.railway_db_url = os.getenv('DATABASE_URL')  # Railway database
        
    def test_connections(self):
        """Test both database connections"""
        results = {
            'local_status': False,
            'railway_status': False,
            'local_error': None,
            'railway_error': None,
            'local_counts': {},
            'railway_counts': {}
        }
        
        # Test local database
        try:
            local_conn = psycopg2.connect(self.local_db_url)
            cursor = local_conn.cursor()
            cursor.execute("SELECT 1")
            results['local_status'] = True
            
            # Get record counts
            cursor.execute("""
                SELECT 
                    (SELECT COUNT(*) FROM bookings) as bookings,
                    (SELECT COUNT(*) FROM guests) as guests,
                    (SELECT COUNT(*) FROM quick_notes) as notes,
                    (SELECT COUNT(*) FROM expenses) as expenses,
                    (SELECT COUNT(*) FROM message_templates) as templates
            """)
            counts = cursor.fetchone()
            results['local_counts'] = {
                'bookings': counts[0],
                'guests': counts[1], 
                'notes': counts[2],
                'expenses': counts[3],
                'templates': counts[4]
            }
            
            local_conn.close()
        except Exception as e:
            results['local_error'] = str(e)
        
        # Test Railway database
        try:
            railway_conn = psycopg2.connect(self.railway_db_url)
            cursor = railway_conn.cursor()
            cursor.execute("SELECT 1")
            results['railway_status'] = True
            
            # Get record counts
            cursor.execute("""
                SELECT 
                    (SELECT COUNT(*) FROM bookings) as bookings,
                    (SELECT COUNT(*) FROM guests) as guests,
                    (SELECT COUNT(*) FROM quick_notes) as notes,
                    (SELECT COUNT(*) FROM expenses) as expenses,
                    (SELECT COUNT(*) FROM message_templates) as templates
            """)
            counts = cursor.fetchone()
            results['railway_counts'] = {
                'bookings': counts[0],
                'guests': counts[1],
                'notes': counts[2], 
                'expenses': counts[3],
                'templates': counts[4]
            }
            
            railway_conn.close()
        except Exception as e:
            results['railway_error'] = str(e)
            
        return results
    
    def create_missing_columns(self, conn):
        """Ensure Railway database has all required columns"""
        cursor = conn.cursor()
        
        try:
            # Add arrival confirmation columns if missing
            cursor.execute("""
                ALTER TABLE bookings 
                ADD COLUMN IF NOT EXISTS arrival_confirmed BOOLEAN DEFAULT FALSE NOT NULL,
                ADD COLUMN IF NOT EXISTS arrival_confirmed_at TIMESTAMP NULL;
            """)
            
            # Add collected_amount if missing
            cursor.execute("""
                ALTER TABLE bookings 
                ADD COLUMN IF NOT EXISTS collected_amount DECIMAL(12, 2) DEFAULT 0.00 NOT NULL;
            """)
            
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            current_app.logger.error(f"Schema update error: {e}")
            return False
        finally:
            cursor.close()
    
    def clean_data_for_import(self, df, table_name):
        """Clean data based on table requirements"""
        if table_name == 'guests':
            # Fix email constraints
            df.loc[df['email'].isna() | (df['email'] == ''), 'email'] = None
            # Remove invalid emails
            invalid_emails = df[df['email'].notna() & ~df['email'].str.contains('@', na=False)]
            if not invalid_emails.empty:
                df = df[~df.index.isin(invalid_emails.index)]
                
        elif table_name == 'bookings':
            # Fix timestamp columns
            timestamp_columns = ['arrival_confirmed_at', 'created_at', 'updated_at']
            for col in timestamp_columns:
                if col in df.columns:
                    df[col] = df[col].replace({pd.NaT: None, 'NaT': None, '': None})
                    df[col] = pd.to_datetime(df[col], errors='coerce')
                    df.loc[df[col].isna(), col] = None
            
            # Ensure boolean columns
            if 'arrival_confirmed' in df.columns:
                df['arrival_confirmed'] = df['arrival_confirmed'].fillna(False).astype(bool)
                
        elif table_name == 'arrival_times':
            # Fix timestamps and dates
            timestamp_columns = ['created_at', 'updated_at']
            for col in timestamp_columns:
                if col in df.columns:
                    df[col] = df[col].replace({pd.NaT: None, 'NaT': None, '': None})
                    df[col] = pd.to_datetime(df[col], errors='coerce')
                    df.loc[df[col].isna(), col] = None
            
            if 'arrival_date' in df.columns:
                df['arrival_date'] = pd.to_datetime(df['arrival_date'], errors='coerce').dt.date
                df.loc[df['arrival_date'].isna(), 'arrival_date'] = None
        
        return df
    
    def import_table_data(self, railway_conn, table_name, df):
        """Import DataFrame to Railway table"""
        if df.empty:
            return False, []
        
        cursor = railway_conn.cursor()
        
        try:
            # Get existing columns
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = %s AND table_schema = 'public'
            """, (table_name,))
            
            existing_columns = [row[0] for row in cursor.fetchall()]
            
            # Filter DataFrame columns
            df_columns = [col for col in df.columns if col in existing_columns]
            df_filtered = df[df_columns].copy()
            
            # Clear existing data
            cursor.execute(f"TRUNCATE TABLE {table_name} RESTART IDENTITY CASCADE")
            
            # Insert new data
            imported_ids = []
            for _, row in df_filtered.iterrows():
                # Handle NULL values properly
                values = []
                for val in row.values:
                    if pd.isna(val) or val is None or str(val) == 'NaT':
                        values.append(None)
                    else:
                        values.append(val)
                
                columns = ', '.join(row.index)
                placeholders = ', '.join(['%s'] * len(row))
                query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders}) RETURNING *"
                cursor.execute(query, tuple(values))
                result = cursor.fetchone()
                if result:
                    imported_ids.append(result[0])
            
            railway_conn.commit()
            return True, imported_ids
            
        except Exception as e:
            railway_conn.rollback()
            current_app.logger.error(f"Import failed for {table_name}: {e}")
            return False, []
        finally:
            cursor.close()
    
    def sync_from_local_to_railway(self):
        """Main sync function from local to Railway"""
        sync_result = {
            'success': False,
            'message': '',
            'details': {},
            'errors': []
        }
        
        try:
            # Connect to databases
            local_conn = psycopg2.connect(self.local_db_url)
            railway_conn = psycopg2.connect(self.railway_db_url)
            
            # Update Railway schema
            if not self.create_missing_columns(railway_conn):
                sync_result['errors'].append("Failed to update Railway schema")
            
            # Define tables in dependency order
            tables = ['guests', 'bookings', 'quick_notes', 'expenses', 'expense_categories', 'message_templates', 'arrival_times']
            
            sync_result['details'] = {}
            
            # Export from local and import to Railway
            for table in tables:
                try:
                    # Export from local
                    df = pd.read_sql_query(f"SELECT * FROM {table}", local_conn)
                    
                    # Clean data
                    df = self.clean_data_for_import(df, table)
                    
                    # Import to Railway
                    success, imported_ids = self.import_table_data(railway_conn, table, df)
                    
                    sync_result['details'][table] = {
                        'exported': len(df),
                        'imported': len(imported_ids) if success else 0,
                        'success': success
                    }
                    
                    if not success:
                        sync_result['errors'].append(f"Failed to import {table}")
                        
                except Exception as e:
                    sync_result['errors'].append(f"Error processing {table}: {str(e)}")
                    sync_result['details'][table] = {'exported': 0, 'imported': 0, 'success': False}
            
            # Close connections
            local_conn.close()
            railway_conn.close()
            
            # Check overall success
            if len(sync_result['errors']) == 0:
                sync_result['success'] = True
                sync_result['message'] = "Data synchronization completed successfully"
            else:
                sync_result['message'] = f"Sync completed with {len(sync_result['errors'])} errors"
            
        except Exception as e:
            sync_result['message'] = f"Sync failed: {str(e)}"
            sync_result['errors'].append(str(e))
        
        return sync_result