import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

# Email configuration - set these in your environment variables
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")  # Your email
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")  # Your app password
FROM_EMAIL = os.getenv("FROM_EMAIL", SMTP_USERNAME)
FROM_NAME = os.getenv("FROM_NAME", "Your App Name")

def send_password_reset_email(email: str, reset_link: str, user_name: str) -> bool:
    """
    Send password reset email to user.
    
    Args:
        email (str): Recipient email address
        reset_link (str): Password reset link
        user_name (str): User's full name
        
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        if not SMTP_USERNAME or not SMTP_PASSWORD:
            print("SMTP credentials not configured")
            return False
            
        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Reset Your Password"
        msg["From"] = f"{FROM_NAME} <{FROM_EMAIL}>"
        msg["To"] = email
        
        # HTML email template
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Reset Your Password</title>
        </head>
        <body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f4f4f4;">
            <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; padding: 20px;">
                <div style="text-align: center; padding: 20px 0; background: linear-gradient(135deg, #1f2937 0%, #374151 100%); margin: -20px -20px 30px -20px;">
                    <h1 style="color: #ffffff; margin: 0; font-size: 24px;">Password Reset Request</h1>
                </div>
                
                <div style="padding: 0 20px;">
                    <p style="color: #333333; font-size: 16px; line-height: 1.6;">
                        Hi {user_name},
                    </p>
                    
                    <p style="color: #333333; font-size: 16px; line-height: 1.6;">
                        We received a request to reset your password. If you didn't make this request, you can safely ignore this email.
                    </p>
                    
                    <p style="color: #333333; font-size: 16px; line-height: 1.6;">
                        To reset your password, click the button below:
                    </p>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{reset_link}" 
                           style="background-color: #000000; color: #ffffff; padding: 12px 30px; text-decoration: none; border-radius: 5px; font-size: 16px; display: inline-block;">
                            Reset My Password
                        </a>
                    </div>
                    
                    <p style="color: #666666; font-size: 14px; line-height: 1.6;">
                        If the button doesn't work, you can copy and paste this link into your browser:
                    </p>
                    
                    <p style="color: #666666; font-size: 14px; word-break: break-all; background-color: #f8f9fa; padding: 10px; border-radius: 4px;">
                        {reset_link}
                    </p>
                    
                    <p style="color: #666666; font-size: 14px; line-height: 1.6; margin-top: 30px;">
                        <strong>Security Notice:</strong> This link will expire in 15 minutes for your security. If you need a new reset link, please request one from the login page.
                    </p>
                    
                    <hr style="border: none; border-top: 1px solid #eeeeee; margin: 30px 0;">
                    
                    <p style="color: #999999; font-size: 12px; text-align: center;">
                        If you didn't request this password reset, please ignore this email or contact support if you have concerns.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Plain text version
        text_body = f"""
        Hi {user_name},

        We received a request to reset your password. If you didn't make this request, you can safely ignore this email.

        To reset your password, copy and paste this link into your browser:
        {reset_link}

        This link will expire in 15 minutes for your security.

        If you didn't request this password reset, please ignore this email or contact support if you have concerns.
        """
        
        # Create text and HTML parts
        part1 = MIMEText(text_body, "plain")
        part2 = MIMEText(html_body, "html")
        
        # Add parts to message
        msg.attach(part1)
        msg.attach(part2)
        
        # Send email
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
            
        print(f"Password reset email sent successfully to {email}")
        return True
        
    except Exception as e:
        print(f"Failed to send password reset email: {str(e)}")
        return False


def send_test_email(to_email: str) -> bool:
    """
    Send a test email to verify SMTP configuration.
    
    Args:
        to_email (str): Email address to send test email to
        
    Returns:
        bool: True if test email sent successfully, False otherwise
    """
    try:
        msg = MIMEText("This is a test email to verify SMTP configuration.")
        msg["Subject"] = "Test Email"
        msg["From"] = f"{FROM_NAME} <{FROM_EMAIL}>"
        msg["To"] = to_email
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
            
        print(f"Test email sent successfully to {to_email}")
        return True
        
    except Exception as e:
        print(f"Failed to send test email: {str(e)}")
        return False
    
    