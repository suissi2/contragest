class ContragestError(Exception):
    """Base class for all Contragest exceptions."""
    pass

class EmailError(ContragestError):
    """Base class for email-related errors."""
    pass

class EmailConnectionError(EmailError):
    """Raised when connection to SMTP server fails."""
    pass

class EmailAuthenticationError(EmailError):
    """Raised when SMTP authentication fails."""
    pass

class EmailSendingError(EmailError):
    """Raised when sending a specific message fails."""
    pass

class EmailConfigError(EmailError):
    """Raised when email configuration is invalid."""
    pass
