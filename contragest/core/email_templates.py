import re
from typing import Dict, Any

class EmailTemplateManager:
    """
    Manages HTML email templates with dynamic variable replacement.
    """
    
    TEMPLATES = {
        'activation': """
        <html><body>
            <div style="font-family: sans-serif; max-width: 600px; margin: auto; border: 1px solid #eee; padding: 20px;">
                <h2 style="color: #2c3e50;">Welcome to Contragest!</h2>
                <p>Hi {{username}},</p>
                <p>To finalize your account setup, please use the following activation code:</p>
                <div style="background: #f8f9fa; padding: 20px; text-align: center; border-radius: 8px;">
                    <h1 style="letter-spacing: 5px; color: #3498db; margin: 0;">{{otp}}</h1>
                </div>
                <p style="color: #7f8c8d; font-size: 14px; margin-top: 20px;">
                    This code will expire in 10 minutes. 
                    If you didn't create an account, you can safely ignore this email.
                </p>
            </div>
        </body></html>
        """,
        
        'password_reset': """
        <html><body>
            <div style="font-family: sans-serif; max-width: 600px; margin: auto; border: 1px solid #eee; padding: 20px;">
                <h2 style="color: #c0392b;">Password Reset Requested</h2>
                <p>Hi {{username}},</p>
                <p>You requested a password reset. Please use the code below to set a new password:</p>
                <div style="background: #fff5f5; padding: 20px; text-align: center; border-radius: 8px; border: 1px solid #feb2b2;">
                    <h1 style="letter-spacing: 5px; color: #e53e3e; margin: 0;">{{otp}}</h1>
                </div>
                <p style="color: #7f8c8d; font-size: 14px; margin-top: 20px;">
                    <strong>Security Warning:</strong> Never share this code with anyone. 
                    The code is valid for 10 minutes.
                </p>
                <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                <p style="font-size: 12px; color: #a0aec0;">If you did not request this reset, your account is still secure.</p>
            </div>
        </body></html>
        """,
        
        'alert': """
        <html>
        <head>
            <style>
                .header { background-color: #2c3e50; padding: 20px; text-align: center; color: white; border-radius: 8px 8px 0 0; }
                .logo { max-height: 80px; margin-bottom: 10px; }
                .content { padding: 30px; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 8px 8px; }
                .section-title { font-size: 18px; font-weight: bold; color: #2d3748; margin-top: 25px; margin-bottom: 15px; border-bottom: 2px solid #edf2f7; padding-bottom: 5px; }
                .section-expiring { color: #d97706; }
                .section-expired { color: #dc2626; }
                table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
                th { text-align: left; padding: 12px; background-color: #f8fafc; color: #64748b; font-size: 13px; text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 1px solid #e2e8f0; }
                td { padding: 12px; border-bottom: 1px solid #f1f5f9; color: #334155; font-size: 14px; }
                .footer { text-align: center; margin-top: 30px; color: #94a3b8; font-size: 12px; }
                .status-pill { padding: 4px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600; text-transform: uppercase; }
                .bg-warning { background-color: #fef3c7; color: #92400e; }
                .bg-danger { background-color: #fee2e2; color: #991b1b; }
            </style>
        </head>
        <body style="font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f3f4f6; padding: 20px;">
            <div style="max-width: 650px; margin: auto; background-color: white; border-radius: 8px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
                <div class="header">
                    <img src="cid:company_logo" class="logo" alt="Company Logo">
                    <h1 style="margin: 0; font-size: 24px;">Contragest Alert</h1>
                </div>
                <div class="content">
                    <p style="color: #475569; line-height: 1.6;">Hello,</p>
                    <p style="color: #475569; line-height: 1.6;">Please review the status of the following contracts. Immediate action may be required for expired items.</p>
                    
                    {{sections}}

                    <p style="margin-top: 30px; color: #475569;">To manage these contracts, please log in to the Contragest Dashboard.</p>
                </div>
                <div class="footer">
                    &copy; {{year}} Contragest - Professional Contract Management Systems
                </div>
            </div>
        </body>
        </html>
        """
    }

    @classmethod
    def render(cls, template_name: str, context: Dict[str, Any]) -> str:
        """
        Renders a template with the given context.
        """
        template = cls.TEMPLATES.get(template_name)
        if not template:
            raise ValueError(f"Template '{template_name}' not found.")
            
        rendered = template
        for key, value in context.items():
            # Basic string replacement
            rendered = rendered.replace(f"{{{{{key}}}}}", str(value))
            
        return rendered
