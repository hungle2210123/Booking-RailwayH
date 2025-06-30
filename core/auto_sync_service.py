"""
Automatic Bidirectional Database Synchronization Service
Handles real-time sync between local PostgreSQL and Railway PostgreSQL
"""

import os
import time
import asyncio
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json
import logging
from dataclasses import dataclass
from sqlalchemy import create_engine, text, MetaData, Table
import pandas as pd

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class SyncStatus:
    """Status of database synchronization"""
    local_count: int
    railway_count: int
    last_sync_time: Optional[datetime]
    sync_needed: bool
    recommended_direction: str  # 'local_to_railway', 'railway_to_local', 'bidirectional', 'none'
    differences: Dict[str, Dict]

class AutoSyncService:
    """Automatic bidirectional database synchronization service"""
    
    def __init__(self):
        # Smart database URL detection for Railway deployment
        database_url = os.getenv('DATABASE_URL')
        
        self.local_url = os.getenv('LOCAL_DATABASE_URL')
        self.railway_url = os.getenv('RAILWAY_DATABASE_URL') or database_url
        
        # On Railway, use DATABASE_URL for both if no specific URLs provided
        if not self.local_url and not self.railway_url and database_url:
            self.railway_url = database_url
            logger.info("🚂 Railway deployment detected: Using DATABASE_URL for sync")
        
        self.sync_interval = int(os.getenv('AUTO_SYNC_INTERVAL', '300'))  # 5 minutes default
        self.is_running = False
        self.sync_thread = None
        self.last_check_time = None
        self.sync_history = []
        
        # Cache for status calculations to improve performance
        self._last_status_cache = None
        self._last_status_time = None
        self._cache_duration = 30  # Cache for 30 seconds
        
        # Tables to monitor for changes
        self.monitored_tables = [
            'bookings',
            'expenses', 
            'quick_notes',
            'message_templates'
        ]
        
        # Initialize database connections
        self.local_engine = None
        self.railway_engine = None
        self._initialize_connections()
    
    def _initialize_connections(self):
        """Initialize database connections"""
        try:
            if self.local_url:
                self.local_engine = create_engine(self.local_url)
                logger.info("✅ Local database connection initialized")
            
            if self.railway_url:
                self.railway_engine = create_engine(self.railway_url)
                logger.info("✅ Railway database connection initialized")
                
        except Exception as e:
            logger.error(f"❌ Database connection error: {e}")
    
    def get_table_counts(self, engine) -> Dict[str, int]:
        """Get record counts for all monitored tables"""
        counts = {}
        
        try:
            with engine.connect() as conn:
                for table in self.monitored_tables:
                    try:
                        result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                        counts[table] = result.scalar()
                    except Exception as e:
                        logger.warning(f"⚠️ Could not count {table}: {e}")
                        counts[table] = 0
        except Exception as e:
            logger.error(f"❌ Error getting table counts: {e}")
            
        return counts
    
    def get_table_last_modified(self, engine, table: str) -> Optional[datetime]:
        """Get last modified timestamp for a table"""
        try:
            with engine.connect() as conn:
                # Try common timestamp columns
                timestamp_columns = ['updated_at', 'created_at', 'date_added', 'timestamp']
                
                for col in timestamp_columns:
                    try:
                        result = conn.execute(text(f"SELECT MAX({col}) FROM {table}"))
                        timestamp = result.scalar()
                        if timestamp:
                            return timestamp
                    except:
                        continue
                        
        except Exception as e:
            logger.warning(f"⚠️ Could not get last modified for {table}: {e}")
            
        return None
    
    def analyze_sync_status(self, force_refresh: bool = False) -> SyncStatus:
        """Analyze current sync status between local and Railway"""
        
        # 🚀 ENHANCED: More aggressive cache invalidation
        current_time = time.time()
        cache_valid = (not force_refresh and self._last_status_cache and self._last_status_time and 
                      current_time - self._last_status_time < self._cache_duration)
        
        if cache_valid:
            logger.info("🔍 Using cached sync status")
            return self._last_status_cache
            
        if force_refresh:
            logger.info("🔍 Analyzing sync status (FORCE REFRESH - bypassing all caches)...")
        else:
            logger.info("🔍 Analyzing sync status (fresh calculation)...")
        
        # Get counts from both databases (handle single database deployments)
        local_counts = self.get_table_counts(self.local_engine) if self.local_engine else {}
        railway_counts = self.get_table_counts(self.railway_engine) if self.railway_engine else {}
        
        # For Railway-only deployment, show status but indicate no sync needed
        if not self.local_engine and self.railway_engine:
            logger.info("🚂 Railway-only deployment: Auto sync disabled")
            return SyncStatus(
                local_count=0,
                railway_count=sum(railway_counts.values()),
                last_sync_time=self.last_check_time,
                sync_needed=False,
                recommended_direction='none',
                differences={}
            )
        
        # Calculate totals
        local_total = sum(local_counts.values())
        railway_total = sum(railway_counts.values())
        
        # Determine sync direction needed
        sync_needed = False
        recommended_direction = 'none'
        differences = {}
        
        for table in self.monitored_tables:
            local_count = local_counts.get(table, 0)
            railway_count = railway_counts.get(table, 0)
            
            if local_count != railway_count:
                sync_needed = True
                differences[table] = {
                    'local': local_count,
                    'railway': railway_count,
                    'difference': abs(local_count - railway_count)
                }
        
        # Determine recommended sync direction
        if sync_needed:
            if local_total > railway_total:
                recommended_direction = 'local_to_railway'
            elif railway_total > local_total:
                recommended_direction = 'railway_to_local' 
            else:
                recommended_direction = 'bidirectional'  # Same totals but different distributions
        
        # Create status object
        status = SyncStatus(
            local_count=local_total,
            railway_count=railway_total,
            last_sync_time=self.last_check_time,
            sync_needed=sync_needed,
            recommended_direction=recommended_direction,
            differences=differences
        )
        
        # 🚀 ENHANCED: Only cache if not force refresh (ensures fresh data when needed)
        if not force_refresh:
            self._last_status_cache = status
            self._last_status_time = current_time
            logger.debug("💾 Cached sync status for future requests")
        else:
            logger.debug("🚫 Not caching due to force_refresh=True")
        
        return status
    
    def export_table_data(self, engine, table: str) -> pd.DataFrame:
        """Export table data to DataFrame"""
        try:
            with engine.connect() as conn:
                df = pd.read_sql_table(table, conn)
                logger.info(f"📊 Exported {len(df)} records from {table}")
                return df
        except Exception as e:
            logger.error(f"❌ Error exporting {table}: {e}")
            return pd.DataFrame()
    
    def import_table_data(self, engine, table: str, df: pd.DataFrame, sync_mode: str = 'append'):
        """Import DataFrame to table with proper error handling and transaction management"""
        try:
            if df.empty:
                logger.warning(f"⚠️ No data to import for {table}")
                return {'success': True, 'message': 'No data to import', 'records_processed': 0}
            
            # Clean DataFrame to handle NaT and other problematic values
            df = self._clean_dataframe(df)
                
            with engine.connect() as conn:
                # Handle different sync modes
                if sync_mode == 'replace':
                    # Clear table first in its own transaction
                    trans = conn.begin()
                    try:
                        conn.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE"))
                        df.to_sql(table, conn, if_exists='append', index=False)
                        trans.commit()
                        logger.info(f"✅ Replaced {len(df)} records in {table}")
                        return {'success': True, 'message': f'Replaced {len(df)} records', 'records_processed': len(df)}
                    except Exception as e:
                        trans.rollback()
                        raise e
                    
                elif sync_mode == 'append':
                    # Add only new records in transaction
                    trans = conn.begin()
                    try:
                        df.to_sql(table, conn, if_exists='append', index=False)
                        trans.commit()
                        logger.info(f"✅ Appended {len(df)} records to {table}")
                        return {'success': True, 'message': f'Appended {len(df)} records', 'records_processed': len(df)}
                    except Exception as e:
                        trans.rollback()
                        raise e
                    
                elif sync_mode == 'upsert':
                    # Smart merge (update existing, insert new) - NO outer transaction for individual record control
                    result = self._upsert_table_data(conn, table, df)
                    # Note: _upsert_table_data now handles its own transactions per record
                    return result
                    
                return {'success': False, 'message': f'Unknown sync mode: {sync_mode}', 'records_processed': 0}
                
        except Exception as e:
            logger.error(f"❌ Error importing to {table}: {e}")
            return {'success': False, 'message': str(e), 'records_processed': 0}
    
    def _upsert_table_data(self, conn, table: str, df: pd.DataFrame):
        """Smart upsert operation for table data with proper PostgreSQL UPSERT and detailed tracking"""
        records_processed = 0
        errors = []
        
        try:
            if table == 'bookings' and 'booking_id' in df.columns:
                # Use PostgreSQL ON CONFLICT for bookings
                records_processed = self._upsert_postgresql_records(conn, table, df, 'booking_id')
                
            elif table == 'quick_notes' and 'note_id' in df.columns:
                # Fix sequence first to prevent conflicts
                sequence_fixed = self._fix_table_sequence(conn, table, 'note_id', 'quick_notes_note_id_seq')
                if not sequence_fixed:
                    errors.append("Failed to fix sequence for quick_notes")
                # Use PostgreSQL ON CONFLICT for quick_notes
                records_processed = self._upsert_postgresql_records(conn, table, df, 'note_id')
                
            elif table == 'guests' and 'guest_id' in df.columns:
                # Fix sequence first to prevent conflicts
                sequence_fixed = self._fix_table_sequence(conn, table, 'guest_id', 'guests_guest_id_seq')
                if not sequence_fixed:
                    errors.append("Failed to fix sequence for guests")
                # Use PostgreSQL ON CONFLICT for guests
                records_processed = self._upsert_postgresql_records(conn, table, df, 'guest_id')
                
            else:
                # For other tables, use manual check and upsert
                logger.warning(f"⚠️ Using manual upsert for {table} - consider adding specific logic")
                records_processed = self._manual_upsert(conn, table, df)
                
            if errors:
                error_msg = f"Upserted {records_processed} records to {table} with warnings: {'; '.join(errors)}"
                logger.warning(f"⚠️ {error_msg}")
                return {'success': True, 'message': error_msg, 'records_processed': records_processed, 'warnings': errors}
            else:
                success_msg = f"Successfully upserted {records_processed} records to {table}"
                logger.info(f"✅ {success_msg}")
                return {'success': True, 'message': success_msg, 'records_processed': records_processed}
                
        except Exception as e:
            error_msg = f"Upsert error for {table}: {e}"
            logger.error(f"❌ {error_msg}")
            return {'success': False, 'message': error_msg, 'records_processed': records_processed}
    
    def _upsert_postgresql_records(self, conn, table: str, df: pd.DataFrame, primary_key: str):
        """Use PostgreSQL's INSERT ON CONFLICT UPDATE for efficient upserts with enhanced error handling"""
        if df.empty:
            return 0
            
        records_processed = 0
        failed_records = []
        
        # Build column list excluding primary key for updates
        update_columns = [col for col in df.columns if col != primary_key]
        
        # Build the UPSERT SQL
        columns = ', '.join(df.columns)
        values_placeholders = ', '.join([f":{col}" for col in df.columns])
        
        # Build the ON CONFLICT UPDATE clause
        if update_columns:
            update_clause = ', '.join([f"{col} = EXCLUDED.{col}" for col in update_columns])
            upsert_sql = f"""
                INSERT INTO {table} ({columns}) 
                VALUES ({values_placeholders})
                ON CONFLICT ({primary_key}) 
                DO UPDATE SET {update_clause}
            """
        else:
            # If only primary key, just ignore conflicts
            upsert_sql = f"""
                INSERT INTO {table} ({columns}) 
                VALUES ({values_placeholders})
                ON CONFLICT ({primary_key}) 
                DO NOTHING
            """
        
        # 🚀 CRITICAL FIX: Individual transactions to prevent InFailedSqlTransaction cascade
        logger.info(f"🚀 Processing {len(df)} records individually with separate transactions for {table}")
        
        # Process each record in its own transaction to prevent cascade failures
        for i, row in df.iterrows():
            primary_key_value = row.get(primary_key, 'unknown')
            clean_row_data = None
            
            try:
                clean_row_data = self._clean_row_data(row.to_dict())
                
                # Special handling for bookings table
                if table == 'bookings':
                    clean_row_data = self._clean_booking_data(clean_row_data)
                
                # 🚀 CRITICAL: Use autocommit for individual records to avoid transaction state issues
                with conn.begin() as transaction:
                    conn.execute(text(upsert_sql), clean_row_data)
                    # Transaction auto-commits on successful exit
                    
                records_processed += 1
                
                if records_processed % 10 == 0:
                    logger.info(f"✅ Processed {records_processed}/{len(df)} records for {table}")
                    
            except Exception as row_error:
                error_msg = str(row_error)
                logger.warning(f"⚠️ Record {primary_key}={primary_key_value} failed: {error_msg}")
                
                # 🛠️ ENHANCED: Try fallback strategies with fresh transaction
                fallback_success = False
                if clean_row_data:  # Only try fallback if we have clean data
                    try:
                        with conn.begin() as fallback_transaction:
                            if self._handle_constraint_violation_with_transaction(conn, table, clean_row_data, primary_key_value, upsert_sql, error_msg):
                                # Transaction auto-commits on successful exit
                                fallback_success = True
                                records_processed += 1
                                logger.info(f"✅ Fallback successful for {primary_key}={primary_key_value}")
                    except Exception as fallback_error:
                        logger.error(f"❌ Fallback failed for {primary_key}={primary_key_value}: {fallback_error}")
                
                if not fallback_success:
                    # If all attempts fail, record the failure
                    failed_records.append(f"{primary_key}={primary_key_value}: {error_msg}")
                    logger.error(f"❌ All attempts failed for record {primary_key}={primary_key_value}: {error_msg}")
        
        if failed_records:
            logger.warning(f"⚠️ {len(failed_records)} records failed to upsert in {table}")
            for failure in failed_records[:5]:  # Log first 5 failures
                logger.warning(f"   - {failure}")
        
        logger.info(f"📊 UPSERT RESULT for {table}: {records_processed}/{len(df)} records processed successfully")
        return records_processed
    
    def _handle_constraint_violation_with_transaction(self, conn, table: str, row_data: dict, primary_key_value: str, upsert_sql: str, error_msg: str) -> bool:
        """Enhanced constraint violation handler with multiple fallback strategies and transaction management"""
        
        # Strategy 1: Try with minimal data for bookings
        if table == 'bookings' and ('constraint' in error_msg.lower() or 'foreign key' in error_msg.lower()):
            try:
                minimal_data = self._get_minimal_booking_data(row_data)
                conn.execute(text(upsert_sql), minimal_data)
                return True
            except Exception as fallback_error:
                logger.warning(f"⚠️ Minimal data fallback failed: {fallback_error}")
        
        # Strategy 2: Try without problematic fields
        if 'null value' in error_msg.lower() or 'not null' in error_msg.lower():
            try:
                # Remove fields that might be NULL
                safe_data = {k: v for k, v in row_data.items() if v is not None and v != ''}
                if table == 'bookings':
                    # Ensure required booking fields have defaults
                    safe_data.update({
                        'room_amount': safe_data.get('room_amount', 0.0),
                        'guest_name': safe_data.get('guest_name', 'Unknown Guest'),
                        'status': safe_data.get('status', 'OK')
                    })
                
                conn.execute(text(upsert_sql), safe_data)
                return True
            except Exception as safe_error:
                logger.warning(f"⚠️ NULL-safe fallback failed: {safe_error}")
        
        # Strategy 3: Try UPDATE only (in case record exists but INSERT fails)
        if table == 'bookings':
            try:
                update_fields = [k for k in row_data.keys() if k != 'booking_id']
                if update_fields:
                    update_clause = ', '.join([f"{field} = :{field}" for field in update_fields])
                    update_sql = f"UPDATE {table} SET {update_clause} WHERE booking_id = :booking_id"
                    result = conn.execute(text(update_sql), row_data)
                    if result.rowcount > 0:
                        return True
            except Exception as update_error:
                logger.warning(f"⚠️ UPDATE-only fallback failed: {update_error}")
        
        return False
    
    def _fix_table_sequence(self, conn, table: str, id_column: str, sequence_name: str):
        """Fix PostgreSQL sequence for a table to prevent duplicate key violations"""
        try:
            # Get the maximum ID currently in the table
            result = conn.execute(text(f"SELECT COALESCE(MAX({id_column}), 0) FROM {table}"))
            max_id = result.scalar()
            
            # Set the sequence to the next available value
            next_value = max_id + 1
            conn.execute(text(f"SELECT setval('{sequence_name}', {next_value})"))
            
            logger.info(f"🔧 Fixed {table} sequence: next {id_column} will be {next_value}")
            return True
            
        except Exception as e:
            logger.warning(f"⚠️ Could not fix sequence for {table}: {e}")
            return False
    
    def _manual_upsert(self, conn, table: str, df: pd.DataFrame):
        """Manual upsert fallback for tables without specific logic with tracking"""
        # Try to determine primary key from first column
        if df.empty:
            return 0
            
        first_col = df.columns[0]
        logger.info(f"🔄 Manual upsert for {table} using {first_col} as key")
        
        records_processed = 0
        
        for _, row in df.iterrows():
            try:
                key_value = row[first_col]
                
                # Check if exists
                exists = conn.execute(text(f"SELECT 1 FROM {table} WHERE {first_col} = :{first_col}"), 
                                    {first_col: key_value}).fetchone()
                
                clean_row_data = self._clean_row_data(row.to_dict())
                
                if exists:
                    # Update existing
                    update_cols = [f"{col} = :{col}" for col in df.columns if col != first_col]
                    if update_cols:  # Only update if there are columns to update
                        update_sql = f"UPDATE {table} SET {', '.join(update_cols)} WHERE {first_col} = :{first_col}"
                        conn.execute(text(update_sql), clean_row_data)
                else:
                    # Insert new
                    cols = ', '.join(df.columns)
                    vals = ', '.join([f":{col}" for col in df.columns])
                    insert_sql = f"INSERT INTO {table} ({cols}) VALUES ({vals})"
                    conn.execute(text(insert_sql), clean_row_data)
                    
                records_processed += 1
                
            except Exception as row_error:
                logger.error(f"❌ Manual upsert failed for {first_col}={key_value}: {row_error}")
        
        return records_processed
    
    def _clean_row_data(self, row_dict: dict) -> dict:
        """Clean row data to handle NaT, NaN, and other problematic values"""
        import pandas as pd
        import numpy as np
        
        cleaned = {}
        for key, value in row_dict.items():
            # Handle pandas NaT (Not a Time) values
            if pd.isna(value) or (hasattr(value, '__str__') and str(value) == 'NaT'):
                cleaned[key] = None
            # Handle numpy NaN values
            elif isinstance(value, (float, np.floating)) and np.isnan(value):
                cleaned[key] = None
            # Handle pandas Timestamp objects
            elif hasattr(value, 'to_pydatetime'):
                try:
                    cleaned[key] = value.to_pydatetime() if not pd.isna(value) else None
                except:
                    cleaned[key] = None
            else:
                cleaned[key] = value
                
        return cleaned
    
    def _clean_booking_data(self, row_data: dict) -> dict:
        """Special cleaning for booking data to handle constraints"""
        cleaned = row_data.copy()
        
        # Ensure required fields have sensible defaults
        if 'room_amount' in cleaned and (cleaned['room_amount'] is None or cleaned['room_amount'] == ''):
            cleaned['room_amount'] = 0.0
            
        if 'commission' in cleaned and (cleaned['commission'] is None or cleaned['commission'] == ''):
            cleaned['commission'] = 0.0
            
        if 'taxi_amount' in cleaned and (cleaned['taxi_amount'] is None or cleaned['taxi_amount'] == ''):
            cleaned['taxi_amount'] = 0.0
            
        if 'collected_amount' in cleaned and (cleaned['collected_amount'] is None or cleaned['collected_amount'] == ''):
            cleaned['collected_amount'] = 0.0
            
        # Handle email conflicts (make unique if empty)
        if 'email' in cleaned and (cleaned['email'] is None or cleaned['email'] == ''):
            booking_id = cleaned.get('booking_id', 'unknown')
            cleaned['email'] = f"guest{booking_id}@sync-placeholder.local"
            
        # Ensure status has valid value
        if 'status' in cleaned and (cleaned['status'] is None or cleaned['status'] == ''):
            cleaned['status'] = 'OK'
            
        return cleaned
    
    def _get_minimal_booking_data(self, row_data: dict) -> dict:
        """Get minimal booking data with only required fields for fallback"""
        # 🚀 CRITICAL: Use actual database column names from schema
        minimal = {
            'booking_id': row_data.get('booking_id', 'UNKNOWN'),
            'guest_name': row_data.get('guest_name', 'Unknown Guest'),
            'checkin_date': row_data.get('checkin_date') or row_data.get('check_in_date'),
            'checkout_date': row_data.get('checkout_date') or row_data.get('check_out_date'),
            'room_amount': float(row_data.get('room_amount', 0.0)),
            'commission': float(row_data.get('commission', 0.0)),
            'taxi_amount': float(row_data.get('taxi_amount', 0.0)),
            'collected_amount': float(row_data.get('collected_amount', 0.0)),
            'booking_status': row_data.get('booking_status', 'OK'),
            'collector': row_data.get('collector', ''),
            'booking_notes': row_data.get('booking_notes'),
            'arrival_confirmed': bool(row_data.get('arrival_confirmed', False))
        }
        
        # Handle datetime fields safely
        import datetime
        if not minimal['checkin_date']:
            minimal['checkin_date'] = datetime.datetime.now().date()
        if not minimal['checkout_date']:
            minimal['checkout_date'] = datetime.datetime.now().date() + datetime.timedelta(days=1)
            
        # Add timestamps if missing
        now = datetime.datetime.now()
        minimal.setdefault('created_at', row_data.get('created_at', now))
        minimal.setdefault('updated_at', now)
        minimal.setdefault('arrival_confirmed_at', row_data.get('arrival_confirmed_at'))
        
        # Remove guest_id to avoid foreign key issues
        if 'guest_id' in minimal:
            del minimal['guest_id']
        
        return minimal
    
    def _clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean DataFrame to handle NaT, NaN, and other problematic values"""
        import pandas as pd
        import numpy as np
        
        # Create a copy to avoid modifying the original
        cleaned_df = df.copy()
        
        # Replace NaT values with None (which becomes NULL in SQL)
        for col in cleaned_df.columns:
            # Handle datetime columns with NaT
            if cleaned_df[col].dtype == 'datetime64[ns]':
                cleaned_df[col] = cleaned_df[col].where(pd.notna(cleaned_df[col]), None)
            # Handle object columns that might contain NaT strings
            elif cleaned_df[col].dtype == 'object':
                cleaned_df[col] = cleaned_df[col].apply(
                    lambda x: None if (pd.isna(x) or str(x) == 'NaT') else x
                )
            # Handle numeric columns with NaN
            elif cleaned_df[col].dtype in ['float64', 'int64']:
                cleaned_df[col] = cleaned_df[col].where(pd.notna(cleaned_df[col]), None)
        
        logger.debug(f"🧹 Cleaned DataFrame with {len(cleaned_df)} rows")
        return cleaned_df
    
    def sync_local_to_railway(self, tables: List[str] = None) -> Dict:
        """Sync data from local to Railway with detailed reporting"""
        if not self.local_engine or not self.railway_engine:
            error_msg = "Database connections not available"
            logger.error(f"❌ {error_msg}")
            return {
                'success': False,
                'message': error_msg,
                'details': {},
                'total_records': 0
            }
            
        tables_to_sync = tables or self.monitored_tables
        logger.info(f"🔄 Starting local → Railway sync for tables: {tables_to_sync}")
        
        sync_details = {}
        total_records = 0
        successful_tables = []
        failed_tables = []
        
        for table in tables_to_sync:
            try:
                # Export from local
                local_df = self.export_table_data(self.local_engine, table)
                
                if not local_df.empty:
                    # Import to Railway with detailed result
                    import_result = self.import_table_data(self.railway_engine, table, local_df, 'upsert')
                    
                    sync_details[table] = {
                        'local_records': len(local_df),
                        'result': import_result
                    }
                    
                    if import_result['success']:
                        successful_tables.append(table)
                        total_records += import_result['records_processed']
                        logger.info(f"✅ Synced {table}: {import_result['records_processed']} records processed")
                    else:
                        failed_tables.append(table)
                        logger.error(f"❌ Failed to sync {table}: {import_result['message']}")
                else:
                    sync_details[table] = {
                        'local_records': 0,
                        'result': {'success': True, 'message': 'No data to sync', 'records_processed': 0}
                    }
                    successful_tables.append(table)  # Empty table is considered success
                    logger.info(f"📭 {table} is empty, skipping")
                    
            except Exception as e:
                error_msg = f"Error syncing {table}: {e}"
                sync_details[table] = {
                    'local_records': 0,
                    'result': {'success': False, 'message': error_msg, 'records_processed': 0}
                }
                failed_tables.append(table)
                logger.error(f"❌ {error_msg}")
        
        sync_success = len(failed_tables) == 0
        
        # 🚀 ENHANCED: Aggressive cache invalidation and immediate status update
        logger.info("🔄 Performing aggressive cache invalidation...")
        self._last_status_cache = None
        self._last_status_time = None
        self.last_check_time = datetime.now()  # Update last check time
        
        # Force immediate status recalculation to verify sync results
        logger.info("🔍 Forcing immediate status verification...")
        verification_status = self.analyze_sync_status(force_refresh=True)
        logger.info(f"📊 Post-sync verification: Local={verification_status.local_count}, Railway={verification_status.railway_count}, Sync needed={verification_status.sync_needed}")
        
        if sync_success:
            logger.info("✅ Local → Railway sync completed successfully")
        else:
            logger.warning(f"⚠️ Partial sync: {len(successful_tables)}/{len(tables_to_sync)} tables successful")
        
        return {
            'success': sync_success,
            'message': f"Synced {len(successful_tables)}/{len(tables_to_sync)} tables successfully",
            'details': sync_details,
            'total_records': total_records,
            'successful_tables': successful_tables,
            'failed_tables': failed_tables
        }
    
    def sync_railway_to_local(self, tables: List[str] = None) -> Dict:
        """Sync data from Railway to local with detailed reporting"""
        if not self.local_engine or not self.railway_engine:
            error_msg = "Database connections not available"
            logger.error(f"❌ {error_msg}")
            return {
                'success': False,
                'message': error_msg,
                'details': {},
                'total_records': 0
            }
            
        tables_to_sync = tables or self.monitored_tables
        logger.info(f"🔄 Starting Railway → local sync for tables: {tables_to_sync}")
        
        sync_details = {}
        total_records = 0
        successful_tables = []
        failed_tables = []
        
        for table in tables_to_sync:
            try:
                # Export from Railway
                railway_df = self.export_table_data(self.railway_engine, table)
                
                if not railway_df.empty:
                    # Import to local with detailed result
                    import_result = self.import_table_data(self.local_engine, table, railway_df, 'upsert')
                    
                    sync_details[table] = {
                        'railway_records': len(railway_df),
                        'result': import_result
                    }
                    
                    if import_result['success']:
                        successful_tables.append(table)
                        total_records += import_result['records_processed']
                        logger.info(f"✅ Synced {table}: {import_result['records_processed']} records processed")
                    else:
                        failed_tables.append(table)
                        logger.error(f"❌ Failed to sync {table}: {import_result['message']}")
                else:
                    sync_details[table] = {
                        'railway_records': 0,
                        'result': {'success': True, 'message': 'No data to sync', 'records_processed': 0}
                    }
                    successful_tables.append(table)  # Empty table is considered success
                    logger.info(f"📭 {table} is empty, skipping")
                    
            except Exception as e:
                error_msg = f"Error syncing {table}: {e}"
                sync_details[table] = {
                    'railway_records': 0,
                    'result': {'success': False, 'message': error_msg, 'records_processed': 0}
                }
                failed_tables.append(table)
                logger.error(f"❌ {error_msg}")
        
        sync_success = len(failed_tables) == 0
        
        # 🚀 ENHANCED: Aggressive cache invalidation and immediate status update
        logger.info("🔄 Performing aggressive cache invalidation...")
        self._last_status_cache = None
        self._last_status_time = None
        self.last_check_time = datetime.now()  # Update last check time
        
        # Force immediate status recalculation to verify sync results
        logger.info("🔍 Forcing immediate status verification...")
        verification_status = self.analyze_sync_status(force_refresh=True)
        logger.info(f"📊 Post-sync verification: Local={verification_status.local_count}, Railway={verification_status.railway_count}, Sync needed={verification_status.sync_needed}")
        
        if sync_success:
            logger.info("✅ Railway → local sync completed successfully")
        else:
            logger.warning(f"⚠️ Partial sync: {len(successful_tables)}/{len(tables_to_sync)} tables successful")
        
        return {
            'success': sync_success,
            'message': f"Synced {len(successful_tables)}/{len(tables_to_sync)} tables successfully",
            'details': sync_details,
            'total_records': total_records,
            'successful_tables': successful_tables,
            'failed_tables': failed_tables
        }
    
    def perform_smart_sync(self) -> Dict:
        """Perform smart bidirectional sync based on analysis"""
        logger.info("🤖 Starting smart sync analysis...")
        
        status = self.analyze_sync_status()
        sync_result = {
            'timestamp': datetime.now().isoformat(),
            'status': status,
            'actions_taken': [],
            'success': False
        }
        
        if not status.sync_needed:
            logger.info("✅ Databases are already in sync")
            sync_result['success'] = True
            sync_result['actions_taken'].append("No sync needed - databases in sync")
            return sync_result
        
        logger.info(f"🔍 Sync needed: {status.recommended_direction}")
        logger.info(f"📊 Local: {status.local_count}, Railway: {status.railway_count}")
        
        # Perform recommended sync
        if status.recommended_direction == 'local_to_railway':
            sync_details = self.sync_local_to_railway()
            success = sync_details['success']
            sync_result['sync_details'] = sync_details
            sync_result['actions_taken'].append(f"Synced local → Railway: {sync_details['message']}")
            if sync_details['total_records'] > 0:
                sync_result['actions_taken'].append(f"Total records processed: {sync_details['total_records']}")
            
        elif status.recommended_direction == 'railway_to_local':
            sync_details = self.sync_railway_to_local()
            success = sync_details['success']
            sync_result['sync_details'] = sync_details
            sync_result['actions_taken'].append(f"Synced Railway → local: {sync_details['message']}")
            if sync_details['total_records'] > 0:
                sync_result['actions_taken'].append(f"Total records processed: {sync_details['total_records']}")
            
        elif status.recommended_direction == 'bidirectional':
            # More complex - sync table by table based on which has more data
            success = True
            all_sync_details = {}
            total_processed = 0
            
            for table, diff in status.differences.items():
                if diff['local'] > diff['railway']:
                    table_sync = self.sync_local_to_railway([table])
                    all_sync_details[f"{table}_local_to_railway"] = table_sync
                    success = success and table_sync['success']
                    total_processed += table_sync['total_records']
                    sync_result['actions_taken'].append(f"Synced {table}: local → Railway ({table_sync['total_records']} records)")
                elif diff['railway'] > diff['local']:
                    table_sync = self.sync_railway_to_local([table])
                    all_sync_details[f"{table}_railway_to_local"] = table_sync
                    success = success and table_sync['success']
                    total_processed += table_sync['total_records']
                    sync_result['actions_taken'].append(f"Synced {table}: Railway → local ({table_sync['total_records']} records)")
            
            sync_result['sync_details'] = all_sync_details
            sync_result['actions_taken'].append(f"Total bidirectional records processed: {total_processed}")
        else:
            success = False
            sync_result['actions_taken'].append("No sync action determined")
        
        sync_result['success'] = success
        self.last_check_time = datetime.now()
        
        # Add to sync history
        self.sync_history.append(sync_result)
        
        # Keep only last 50 sync records
        if len(self.sync_history) > 50:
            self.sync_history = self.sync_history[-50:]
        
        # Persist sync history to database
        self._persist_sync_history(sync_result)
        
        return sync_result
    
    def start_auto_sync(self):
        """Start automatic sync monitoring"""
        if self.is_running:
            logger.warning("⚠️ Auto sync is already running")
            return
        
        logger.info(f"🚀 Starting auto sync service (interval: {self.sync_interval}s)")
        self.is_running = True
        
        def sync_loop():
            while self.is_running:
                try:
                    sync_result = self.perform_smart_sync()
                    
                    if sync_result['success']:
                        logger.info("✅ Auto sync completed successfully")
                    else:
                        logger.warning("⚠️ Auto sync completed with issues")
                        
                except Exception as e:
                    logger.error(f"❌ Auto sync error: {e}")
                
                # Wait for next interval
                for _ in range(self.sync_interval):
                    if not self.is_running:
                        break
                    time.sleep(1)
        
        self.sync_thread = threading.Thread(target=sync_loop, daemon=True)
        self.sync_thread.start()
        logger.info("✅ Auto sync service started")
    
    def stop_auto_sync(self):
        """Stop automatic sync monitoring"""
        if not self.is_running:
            logger.warning("⚠️ Auto sync is not running")
            return
            
        logger.info("🛑 Stopping auto sync service...")
        self.is_running = False
        
        if self.sync_thread:
            self.sync_thread.join(timeout=5)
        
        logger.info("✅ Auto sync service stopped")
    
    def get_sync_notifications(self) -> List[Dict]:
        """Get sync notifications for UI display"""
        status = self.analyze_sync_status()
        notifications = []
        
        if status.sync_needed:
            if status.recommended_direction == 'local_to_railway':
                notifications.append({
                    'type': 'info',
                    'title': '🔄 Sync Needed: Local → Railway',
                    'message': f'Local has {status.local_count - status.railway_count} more records. Click to sync to Railway.',
                    'action': 'sync_local_to_railway',
                    'priority': 'high' if status.local_count - status.railway_count > 10 else 'medium'
                })
                
            elif status.recommended_direction == 'railway_to_local':
                notifications.append({
                    'type': 'info',
                    'title': '🔄 Sync Needed: Railway → Local',
                    'message': f'Railway has {status.railway_count - status.local_count} more records. Click to sync to local.',
                    'action': 'sync_railway_to_local',
                    'priority': 'high' if status.railway_count - status.local_count > 10 else 'medium'
                })
                
            elif status.recommended_direction == 'bidirectional':
                notifications.append({
                    'type': 'warning',
                    'title': '🔄 Complex Sync Needed',
                    'message': 'Databases have different data distributions. Review and sync manually.',
                    'action': 'show_sync_details',
                    'priority': 'high'
                })
        
        return notifications
    
    def _persist_sync_history(self, sync_result: Dict):
        """Persist sync history to database"""
        try:
            # Try to use Railway database first, fallback to local
            engine = self.railway_engine or self.local_engine
            
            if not engine:
                logger.warning("⚠️ No database available to persist sync history")
                return
            
            # Create sync history table if it doesn't exist
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS sync_history (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                sync_timestamp VARCHAR(50),
                success BOOLEAN,
                recommended_direction VARCHAR(50),
                local_count INTEGER,
                railway_count INTEGER,
                total_records INTEGER DEFAULT 0,
                successful_tables TEXT[],
                failed_tables TEXT[],
                actions_taken TEXT[],
                sync_details JSONB
            )
            """
            
            with engine.connect() as conn:
                conn.execute(text(create_table_sql))
                
                # Extract data from sync_result
                status = sync_result.get('status')
                sync_details = sync_result.get('sync_details', {})
                
                # Calculate totals from sync_details if available
                total_records = 0
                successful_tables = []
                failed_tables = []
                
                if isinstance(sync_details, dict):
                    if 'total_records' in sync_details:
                        total_records = sync_details['total_records']
                        successful_tables = sync_details.get('successful_tables', [])
                        failed_tables = sync_details.get('failed_tables', [])
                    else:
                        # Handle bidirectional sync details
                        for key, details in sync_details.items():
                            if isinstance(details, dict) and 'total_records' in details:
                                total_records += details['total_records']
                                if details['success']:
                                    table_name = key.split('_')[0]  # Extract table name
                                    if table_name not in successful_tables:
                                        successful_tables.append(table_name)
                                else:
                                    table_name = key.split('_')[0]  # Extract table name
                                    if table_name not in failed_tables:
                                        failed_tables.append(table_name)
                
                # Insert sync history record
                insert_sql = """
                INSERT INTO sync_history (
                    sync_timestamp, success, recommended_direction, 
                    local_count, railway_count, total_records,
                    successful_tables, failed_tables, actions_taken, sync_details
                ) VALUES (
                    :sync_timestamp, :success, :recommended_direction,
                    :local_count, :railway_count, :total_records,
                    :successful_tables, :failed_tables, :actions_taken, :sync_details
                )
                """
                
                params = {
                    'sync_timestamp': sync_result.get('timestamp'),
                    'success': sync_result.get('success', False),
                    'recommended_direction': status.recommended_direction if status else 'unknown',
                    'local_count': status.local_count if status else 0,
                    'railway_count': status.railway_count if status else 0,
                    'total_records': total_records,
                    'successful_tables': successful_tables,
                    'failed_tables': failed_tables,
                    'actions_taken': sync_result.get('actions_taken', []),
                    'sync_details': json.dumps(sync_details)
                }
                
                conn.execute(text(insert_sql), params)
                conn.commit()
                
                logger.info(f"💾 Persisted sync history: {total_records} records processed")
                
        except Exception as e:
            logger.error(f"❌ Failed to persist sync history: {e}")
    
    def get_sync_history_from_database(self, limit: int = 20) -> List[Dict]:
        """Retrieve sync history from database"""
        try:
            # Try to use Railway database first, fallback to local
            engine = self.railway_engine or self.local_engine
            
            if not engine:
                logger.warning("⚠️ No database available to retrieve sync history")
                return []
            
            with engine.connect() as conn:
                # Check if table exists
                table_exists = conn.execute(text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'sync_history'
                    )
                """)).scalar()
                
                if not table_exists:
                    logger.info("💾 No sync history table found")
                    return []
                
                # Retrieve sync history
                result = conn.execute(text(f"""
                    SELECT 
                        timestamp, sync_timestamp, success, recommended_direction,
                        local_count, railway_count, total_records,
                        successful_tables, failed_tables, actions_taken, sync_details
                    FROM sync_history 
                    ORDER BY timestamp DESC 
                    LIMIT {limit}
                """))
                
                history = []
                for row in result:
                    try:
                        sync_details = json.loads(row.sync_details) if row.sync_details else {}
                    except:
                        sync_details = {}
                    
                    history.append({
                        'timestamp': row.timestamp.isoformat() if row.timestamp else row.sync_timestamp,
                        'success': row.success,
                        'recommended_direction': row.recommended_direction,
                        'local_count': row.local_count,
                        'railway_count': row.railway_count,
                        'total_records': row.total_records,
                        'successful_tables': list(row.successful_tables or []),
                        'failed_tables': list(row.failed_tables or []),
                        'actions_taken': list(row.actions_taken or []),
                        'sync_details': sync_details
                    })
                
                logger.info(f"💾 Retrieved {len(history)} sync history records")
                return history
                
        except Exception as e:
            logger.error(f"❌ Failed to retrieve sync history: {e}")
            return []
    
    def get_comprehensive_sync_status(self) -> Dict:
        """Get comprehensive sync status including history"""
        current_status = self.analyze_sync_status()
        history = self.get_sync_history_from_database(10)
        
        return {
            'current_status': {
                'local_count': current_status.local_count,
                'railway_count': current_status.railway_count,
                'sync_needed': current_status.sync_needed,
                'recommended_direction': current_status.recommended_direction,
                'differences': current_status.differences,
                'last_check': current_status.last_sync_time.isoformat() if current_status.last_sync_time else None
            },
            'recent_history': history,
            'notifications': self.get_sync_notifications()
        }

# Global instance
auto_sync_service = AutoSyncService()