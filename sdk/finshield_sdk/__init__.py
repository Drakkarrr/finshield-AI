"""FinShield AI Python SDK

Auto-generated client for the FinShield AI API.
Provides type-safe access to all API endpoints with idempotency-preserving retries.

Usage:
    from finshield_sdk import FinShieldClient
    
    client = FinShieldClient(api_key="your-api-key", base_url="https://api.finshield.ai")
    
    # Screen a transaction
    result = client.screen_transaction(
        sender_name="John Doe",
        receiver_name="Jane Smith",
        amount=10000.0,
        currency="USD",
        transaction_type="wire"
    )
    
    print(f"Status: {result.status}, Risk: {result.risk_score}")
"""

__version__ = "1.0.0"

from .client import FinShieldClient
from .models import (
    TransactionRequest,
    TransactionResponse,
    ScreeningResult,
    CaseData,
    RuleDefinition,
    UserProfile,
    CreditsData,
    StatsData,
    HealthData,
)
from .exceptions import (
    FinShieldError,
    AuthenticationError,
    RateLimitError,
    ServerError,
    ValidationError,
)

__all__ = [
    "FinShieldClient",
    "TransactionRequest",
    "TransactionResponse",
    "ScreeningResult",
    "CaseData",
    "RuleDefinition",
    "UserProfile",
    "CreditsData",
    "StatsData",
    "HealthData",
    "FinShieldError",
    "AuthenticationError",
    "RateLimitError",
    "ServerError",
    "ValidationError",
]
