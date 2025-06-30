"""
Auto Sync Triggers
Automatically trigger sync operations when data changes
"""

import logging
from functools import wraps
from datetime import datetime
from typing import Optional
import threading

logger = logging.getLogger(__name__)

class SyncTriggers:
    """Manages automatic sync triggers for data changes"""
    
    def __init__(self, auto_sync_service):
        self.auto_sync_service = auto_sync_service
        self.pending_sync = False
        self.last_trigger_time = None
        self.sync_delay = 10  # Wait 10 seconds before triggering sync
        self.sync_timer = None
        
    def trigger_sync_after_delay(self, operation_type: str = "data_change"):
        """Trigger sync after a short delay to batch multiple operations"""
        
        if not self.auto_sync_service.local_engine or not self.auto_sync_service.railway_engine:
            logger.debug("Sync not triggered - database connections not available")
            return
            
        logger.info(f"📋 Sync trigger: {operation_type}")
        
        # Cancel existing timer if any
        if self.sync_timer:
            self.sync_timer.cancel()
        
        # Set new timer
        self.sync_timer = threading.Timer(self.sync_delay, self._perform_delayed_sync)
        self.sync_timer.daemon = True
        self.sync_timer.start()
        
        self.pending_sync = True
        self.last_trigger_time = datetime.now()
    
    def _perform_delayed_sync(self):
        """Perform the actual sync operation after delay"""
        try:
            if self.pending_sync:
                logger.info("🔄 Performing automatic sync due to data changes...")
                result = self.auto_sync_service.perform_smart_sync()
                
                if result['success']:
                    logger.info("✅ Automatic sync completed successfully")
                else:
                    logger.warning("⚠️ Automatic sync completed with issues")
                
                self.pending_sync = False
                
        except Exception as e:
            logger.error(f"❌ Automatic sync failed: {e}")
    
    def cancel_pending_sync(self):
        """Cancel any pending sync operation"""
        if self.sync_timer:
            self.sync_timer.cancel()
            self.sync_timer = None
        self.pending_sync = False

# Decorator for automatic sync triggers
def trigger_auto_sync(operation_type: str = "data_change"):
    """Decorator to automatically trigger sync after database operations"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Execute the original function
            result = func(*args, **kwargs)
            
            # Try to trigger sync if auto sync service is available
            try:
                from core.auto_sync_service import auto_sync_service
                if hasattr(auto_sync_service, 'sync_triggers'):
                    auto_sync_service.sync_triggers.trigger_sync_after_delay(operation_type)
                else:
                    # Initialize sync triggers if not already done
                    auto_sync_service.sync_triggers = SyncTriggers(auto_sync_service)
                    auto_sync_service.sync_triggers.trigger_sync_after_delay(operation_type)
                    
            except Exception as e:
                logger.debug(f"Could not trigger auto sync: {e}")
            
            return result
        return wrapper
    return decorator

# Convenience decorators for specific operations
def trigger_sync_on_booking_change(func):
    """Trigger sync when booking data changes"""
    return trigger_auto_sync("booking_change")(func)

def trigger_sync_on_expense_change(func):
    """Trigger sync when expense data changes"""
    return trigger_auto_sync("expense_change")(func)

def trigger_sync_on_note_change(func):
    """Trigger sync when notes change"""
    return trigger_auto_sync("note_change")(func)