import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from contextlib import contextmanager


class AuditLogger:
    """Audit logging for security-sensitive operations"""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
    
    def log_audit_event(self, 
                       event_type: str,
                       user_id: Optional[str] = None,
                       resource: Optional[str] = None,
                       action: Optional[str] = None,
                       details: Optional[Dict[str, Any]] = None,
                       success: bool = True):
        """
        Log audit events in structured format
        
        Args:
            event_type: Type of audit event
            user_id: ID of the user performing the action
            resource: Resource being accessed/modified
            action: Action performed
            details: Additional context about the event
            success: Whether the operation succeeded
        """
        
        audit_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'event_type': event_type,
            'user_id': user_id,
            'resource': resource,
            'action': action,
            'details': details or {},
            'success': success,
            'severity': 'INFO' if success else 'ERROR'
        }
        
        # Log as structured JSON
        self.logger.info(json.dumps(audit_data))
    
    @contextmanager
    def audit_context(self, event_type: str, user_id: Optional[str] = None):
        """
        Context manager for logging operations with automatic start/end events
        
        Args:
            event_type: Type of operation being audited
            user_id: ID of the user performing the operation
        """
        
        # Log start of operation
        self.log_audit_event(
            event_type=event_type,
            user_id=user_id,
            action='START',
            success=True
        )
        
        try:
            yield
        except Exception as e:
            # Log failure if exception occurs
            self.log_audit_event(
                event_type=event_type,
                user_id=user_id,
                action='ERROR',
                details={'error': str(e)},
                success=False
            )
            raise
        else:
            # Log successful completion
            self.log_audit_event(
                event_type=event_type,
                user_id=user_id,
                action='SUCCESS',
                success=True
            )


# Global audit logger instance
audit_logger = None


def setup_audit_logging(logger: logging.Logger):
    """Setup audit logging for the application"""
    global audit_logger
    audit_logger = AuditLogger(logger)
    
    # Add a method to the logger for easy access
    def log_audit_event(event_type, user_id=None, resource=None, action=None, 
                       details=None, success=True):
        if audit_logger:
            audit_logger.log_audit_event(
                event_type=event_type,
                user_id=user_id,
                resource=resource,
                action=action,
                details=details,
                success=success
            )
    
    logger.audit = log_audit_event
    
    return logger


def get_audit_logger() -> AuditLogger:
    """Get the audit logger instance"""
    if audit_logger is None:
        raise RuntimeError("Audit logging not initialized. Call setup_audit_logging first.")
    return audit_logger
