"""Email service for transactional emails.

Handles:
- Password reset emails
- Welcome emails
- Email verification
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from jose import jwt

from app.config import get_settings

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending transactional emails."""

    def __init__(self):
        settings = get_settings()
        self.api_key = settings.sendgrid_api_key
        self.from_email = settings.email_from or "noreply@beatsight.io"
        self.from_name = "BeatSight"
        self.frontend_url = settings.frontend_url or "http://localhost:5173"
        self.jwt_secret = settings.jwt_secret_key
        self.jwt_algorithm = settings.jwt_algorithm

    def is_configured(self) -> bool:
        """Check if email service is configured."""
        return bool(self.api_key)

    def _create_password_reset_token(self, user_id: UUID, email: str) -> str:
        """Create a password reset token (valid for 1 hour)."""
        expire = datetime.now(timezone.utc) + timedelta(hours=1)
        payload = {
            "sub": str(user_id),
            "email": email,
            "exp": expire,
            "type": "password_reset",
        }
        return jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)

    def _create_email_verification_token(self, user_id: UUID, email: str) -> str:
        """Create an email verification token (valid for 24 hours)."""
        expire = datetime.now(timezone.utc) + timedelta(hours=24)
        payload = {
            "sub": str(user_id),
            "email": email,
            "exp": expire,
            "type": "email_verification",
        }
        return jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)

    def verify_password_reset_token(self, token: str) -> dict[str, Any] | None:
        """Verify a password reset token and return payload."""
        try:
            payload = jwt.decode(
                token, self.jwt_secret, algorithms=[self.jwt_algorithm]
            )
            if payload.get("type") != "password_reset":
                return None
            return payload
        except Exception:
            return None

    def verify_email_verification_token(self, token: str) -> dict[str, Any] | None:
        """Verify an email verification token and return payload."""
        try:
            payload = jwt.decode(
                token, self.jwt_secret, algorithms=[self.jwt_algorithm]
            )
            if payload.get("type") != "email_verification":
                return None
            return payload
        except Exception:
            return None

    async def _send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str | None = None,
    ) -> bool:
        """Send an email via SendGrid."""
        if not self.is_configured():
            logger.warning("Email not sent - SendGrid not configured")
            # In development, log the email content
            logger.info(f"Would send email to {to_email}: {subject}")
            return True

        try:
            import sendgrid
            from sendgrid.helpers.mail import Mail, Email, To, Content

            sg = sendgrid.SendGridAPIClient(api_key=self.api_key)

            message = Mail(
                from_email=Email(self.from_email, self.from_name),
                to_emails=To(to_email),
                subject=subject,
                html_content=Content("text/html", html_content),
            )

            if text_content:
                message.add_content(Content("text/plain", text_content))

            response = sg.send(message)

            if response.status_code >= 400:
                logger.error(f"SendGrid error: {response.status_code}")
                return False

            logger.info(f"Email sent to {to_email}: {subject}")
            return True

        except ImportError:
            logger.warning("sendgrid package not installed, email not sent")
            return False
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    async def send_password_reset(
        self, user_id: UUID, email: str, display_name: str
    ) -> bool:
        """Send password reset email."""
        token = self._create_password_reset_token(user_id, email)
        reset_url = f"{self.frontend_url}/reset-password?token={token}"

        subject = "Reset your BeatSight password"
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 0; background: #111827; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .card {{ background: #1f2937; border-radius: 12px; overflow: hidden; }}
        .header {{ background: linear-gradient(135deg, #7c3aed, #ec4899); padding: 30px; text-align: center; }}
        .header h1 {{ color: white; margin: 0; font-size: 24px; }}
        .content {{ padding: 30px; color: #d1d5db; }}
        .content p {{ line-height: 1.6; margin: 0 0 16px 0; }}
        .button {{ display: inline-block; background: #7c3aed; color: white !important; padding: 14px 28px; 
                   text-decoration: none; border-radius: 8px; font-weight: 600; margin: 20px 0; }}
        .button:hover {{ background: #6d28d9; }}
        .footer {{ padding: 20px 30px; color: #6b7280; font-size: 12px; border-top: 1px solid #374151; }}
        .muted {{ color: #9ca3af; font-size: 14px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <div class="header">
                <h1>🔐 Password Reset</h1>
            </div>
            <div class="content">
                <p>Hi {display_name},</p>
                <p>We received a request to reset your password. Click the button below to create a new password:</p>
                <p style="text-align: center;">
                    <a href="{reset_url}" class="button">Reset Password</a>
                </p>
                <p class="muted">This link will expire in 1 hour for security reasons.</p>
                <p class="muted">If you didn't request this, you can safely ignore this email.</p>
            </div>
            <div class="footer">
                <p>If the button doesn't work, copy and paste this URL into your browser:</p>
                <p style="word-break: break-all;">{reset_url}</p>
            </div>
        </div>
    </div>
</body>
</html>
"""
        text_content = f"""
Hi {display_name},

We received a request to reset your BeatSight password.

Reset your password: {reset_url}

This link will expire in 1 hour.

If you didn't request this, you can safely ignore this email.
"""
        return await self._send_email(email, subject, html_content, text_content)

    async def send_welcome(self, email: str, display_name: str) -> bool:
        """Send welcome email to new users."""
        subject = "Welcome to BeatSight! 🎵"
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 0; background: #111827; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .card {{ background: #1f2937; border-radius: 12px; overflow: hidden; }}
        .header {{ background: linear-gradient(135deg, #7c3aed, #ec4899); padding: 40px; text-align: center; }}
        .header h1 {{ color: white; margin: 0; font-size: 28px; }}
        .content {{ padding: 30px; color: #d1d5db; }}
        .content p {{ line-height: 1.6; margin: 0 0 16px 0; }}
        .feature {{ display: flex; align-items: flex-start; margin: 16px 0; }}
        .feature-icon {{ width: 40px; height: 40px; background: #374151; border-radius: 8px; 
                        display: flex; align-items: center; justify-content: center; margin-right: 16px; flex-shrink: 0; }}
        .feature-text h3 {{ color: white; margin: 0 0 4px 0; font-size: 16px; }}
        .feature-text p {{ margin: 0; font-size: 14px; }}
        .button {{ display: inline-block; background: #7c3aed; color: white !important; padding: 14px 28px; 
                   text-decoration: none; border-radius: 8px; font-weight: 600; margin: 20px 0; }}
        .footer {{ padding: 20px 30px; color: #6b7280; font-size: 12px; border-top: 1px solid #374151; text-align: center; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <div class="header">
                <h1>Welcome to BeatSight!</h1>
            </div>
            <div class="content">
                <p>Hi {display_name},</p>
                <p>Thanks for joining BeatSight! You're now ready to transform any song into playable drum beatmaps using our AI.</p>
                
                <div class="feature">
                    <div class="feature-icon">🎵</div>
                    <div class="feature-text">
                        <h3>Upload Any Song</h3>
                        <p>MP3, WAV, FLAC - we handle them all</p>
                    </div>
                </div>
                
                <div class="feature">
                    <div class="feature-icon">🤖</div>
                    <div class="feature-text">
                        <h3>AI Transcription</h3>
                        <p>19 drum classes detected with 85% accuracy</p>
                    </div>
                </div>
                
                <div class="feature">
                    <div class="feature-icon">🎮</div>
                    <div class="feature-text">
                        <h3>Play & Practice</h3>
                        <p>Export to osu! or use our desktop app</p>
                    </div>
                </div>
                
                <p style="text-align: center;">
                    <a href="{self.frontend_url}/upload" class="button">Create Your First Beatmap</a>
                </p>
            </div>
            <div class="footer">
                <p>You're receiving this because you signed up for BeatSight.</p>
                <p><a href="{self.frontend_url}/settings/notifications" style="color: #9ca3af;">Manage email preferences</a></p>
            </div>
        </div>
    </div>
</body>
</html>
"""
        text_content = f"""
Hi {display_name},

Welcome to BeatSight! 🎵

You're now ready to transform any song into playable drum beatmaps using our AI.

What you can do:
- Upload any song (MP3, WAV, FLAC)
- AI transcribes drums with 19 classes and 85% accuracy
- Export to osu! or play in our desktop app

Get started: {self.frontend_url}/upload

Happy drumming!
The BeatSight Team
"""
        return await self._send_email(email, subject, html_content, text_content)

    async def send_email_verification(
        self, user_id: UUID, email: str, display_name: str
    ) -> bool:
        """Send email verification link."""
        token = self._create_email_verification_token(user_id, email)
        verify_url = f"{self.frontend_url}/verify-email?token={token}"

        subject = "Verify your BeatSight email"
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 0; background: #111827; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .card {{ background: #1f2937; border-radius: 12px; overflow: hidden; }}
        .header {{ background: linear-gradient(135deg, #7c3aed, #ec4899); padding: 30px; text-align: center; }}
        .header h1 {{ color: white; margin: 0; font-size: 24px; }}
        .content {{ padding: 30px; color: #d1d5db; }}
        .content p {{ line-height: 1.6; margin: 0 0 16px 0; }}
        .button {{ display: inline-block; background: #7c3aed; color: white !important; padding: 14px 28px; 
                   text-decoration: none; border-radius: 8px; font-weight: 600; margin: 20px 0; }}
        .footer {{ padding: 20px 30px; color: #6b7280; font-size: 12px; border-top: 1px solid #374151; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <div class="header">
                <h1>✉️ Verify Your Email</h1>
            </div>
            <div class="content">
                <p>Hi {display_name},</p>
                <p>Please verify your email address to complete your BeatSight account setup:</p>
                <p style="text-align: center;">
                    <a href="{verify_url}" class="button">Verify Email</a>
                </p>
                <p style="color: #9ca3af; font-size: 14px;">This link will expire in 24 hours.</p>
            </div>
            <div class="footer">
                <p>If you didn't create a BeatSight account, you can ignore this email.</p>
            </div>
        </div>
    </div>
</body>
</html>
"""
        text_content = f"""
Hi {display_name},

Please verify your email address: {verify_url}

This link will expire in 24 hours.

If you didn't create a BeatSight account, you can ignore this email.
"""
        return await self._send_email(email, subject, html_content, text_content)

    async def send_subscription_confirmation(
        self, email: str, display_name: str, plan_name: str
    ) -> bool:
        """Send subscription confirmation email."""
        subject = f"Welcome to BeatSight {plan_name}! 🎉"
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 0; background: #111827; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .card {{ background: #1f2937; border-radius: 12px; overflow: hidden; }}
        .header {{ background: linear-gradient(135deg, #7c3aed, #ec4899); padding: 30px; text-align: center; }}
        .header h1 {{ color: white; margin: 0; font-size: 24px; }}
        .content {{ padding: 30px; color: #d1d5db; }}
        .content p {{ line-height: 1.6; margin: 0 0 16px 0; }}
        .plan-badge {{ display: inline-block; background: #7c3aed; color: white; padding: 8px 16px; 
                       border-radius: 20px; font-weight: 600; margin: 10px 0; }}
        .button {{ display: inline-block; background: #7c3aed; color: white !important; padding: 14px 28px; 
                   text-decoration: none; border-radius: 8px; font-weight: 600; margin: 20px 0; }}
        .footer {{ padding: 20px 30px; color: #6b7280; font-size: 12px; border-top: 1px solid #374151; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <div class="header">
                <h1>🎉 Subscription Confirmed!</h1>
            </div>
            <div class="content">
                <p>Hi {display_name},</p>
                <p>Thank you for subscribing to BeatSight!</p>
                <p style="text-align: center;">
                    <span class="plan-badge">{plan_name}</span>
                </p>
                <p>Your subscription is now active. You now have access to:</p>
                <ul style="color: #d1d5db; line-height: 1.8;">
                    <li>Increased AI transcription quota</li>
                    <li>Priority processing queue</li>
                    <li>Advanced export options</li>
                    <li>Premium support</li>
                </ul>
                <p style="text-align: center;">
                    <a href="{self.frontend_url}/upload" class="button">Start Creating</a>
                </p>
            </div>
            <div class="footer">
                <p>Manage your subscription anytime in your <a href="{self.frontend_url}/settings/subscription" style="color: #7c3aed;">account settings</a>.</p>
            </div>
        </div>
    </div>
</body>
</html>
"""
        text_content = f"""
Hi {display_name},

Thank you for subscribing to BeatSight {plan_name}!

Your subscription is now active. You now have access to:
- Increased AI transcription quota
- Priority processing queue
- Advanced export options
- Premium support

Start creating: {self.frontend_url}/upload

Manage your subscription: {self.frontend_url}/settings/subscription

The BeatSight Team
"""
        return await self._send_email(email, subject, html_content, text_content)


# Singleton instance
_email_service: EmailService | None = None


def get_email_service() -> EmailService:
    """Get or create EmailService singleton."""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
