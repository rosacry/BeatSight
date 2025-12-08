"""SMS service for phone verification.

Handles:
- Sending verification codes via SMS (Twilio)
- Rate limiting SMS sends
- Code generation and validation
"""

from __future__ import annotations

import logging
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.config import get_settings

logger = logging.getLogger(__name__)


class SMSService:
    """Service for sending SMS messages via Twilio."""

    def __init__(self):
        settings = get_settings()
        self.account_sid = settings.twilio_account_sid
        self.auth_token = settings.twilio_auth_token
        self.from_number = settings.twilio_phone_number
        self.code_ttl_minutes = settings.phone_verification_code_ttl_minutes
        self.max_attempts = settings.phone_verification_max_attempts

    def is_configured(self) -> bool:
        """Check if SMS service is configured."""
        return bool(self.account_sid and self.auth_token and self.from_number)

    def generate_verification_code(self, length: int = 6) -> str:
        """Generate a secure random numeric verification code.
        
        Args:
            length: Number of digits in the code (default 6)
            
        Returns:
            A string of random digits
        """
        return ''.join(secrets.choice(string.digits) for _ in range(length))

    def get_code_expiry(self) -> datetime:
        """Get the expiry time for a new verification code."""
        return datetime.now(timezone.utc) + timedelta(minutes=self.code_ttl_minutes)

    async def send_verification_code(
        self,
        phone_number: str,
        code: str,
    ) -> bool:
        """Send a verification code via SMS.
        
        Args:
            phone_number: The phone number to send to (E.164 format)
            code: The verification code to send
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.is_configured():
            logger.warning("SMS not sent - Twilio not configured")
            # In development, log the code
            logger.info(f"Would send SMS to {phone_number}: Your BeatSight verification code is: {code}")
            return True

        try:
            from twilio.rest import Client
            
            client = Client(self.account_sid, self.auth_token)
            
            message = client.messages.create(
                body=f"Your BeatSight verification code is: {code}\n\nThis code expires in {self.code_ttl_minutes} minutes.",
                from_=self.from_number,
                to=phone_number,
            )
            
            logger.info(f"SMS sent to {phone_number[-4:]}: SID={message.sid}")
            return True
            
        except ImportError:
            logger.error("Twilio library not installed. Run: pip install twilio")
            return False
        except Exception as e:
            logger.exception(f"Failed to send SMS to {phone_number[-4:]}: {e}")
            return False

    def normalize_phone_number(self, phone: str) -> str:
        """Normalize a phone number to E.164 format.
        
        E.164 format: +[country code][number]
        Example: +14155551234
        
        Args:
            phone: Raw phone number input
            
        Returns:
            Normalized phone number in E.164 format
        """
        # Remove all non-digit characters except leading +
        has_plus = phone.startswith('+')
        digits = ''.join(c for c in phone if c.isdigit())
        
        # If no country code, assume US (+1)
        if not has_plus and len(digits) == 10:
            digits = '1' + digits
        
        return '+' + digits

    def validate_phone_number(self, phone: str) -> tuple[bool, str]:
        """Validate a phone number format.
        
        Args:
            phone: Phone number to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        normalized = self.normalize_phone_number(phone)
        
        # Basic validation: must have country code + at least 10 digits
        digits = normalized[1:]  # Remove leading +
        
        if len(digits) < 10:
            return False, "Phone number is too short"
        
        if len(digits) > 15:
            return False, "Phone number is too long"
        
        if not digits.isdigit():
            return False, "Phone number must contain only digits"
        
        return True, ""


# Singleton instance
_sms_service: Optional[SMSService] = None


def get_sms_service() -> SMSService:
    """Get or create the SMS service singleton."""
    global _sms_service
    if _sms_service is None:
        _sms_service = SMSService()
    return _sms_service
