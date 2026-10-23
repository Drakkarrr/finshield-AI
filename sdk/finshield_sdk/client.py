"""FinShield SDK Client with idempotency-preserving retries."""

import time
import uuid
import httpx
from typing import Optional, Any
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
    NotFoundError,
)


class FinShieldClient:
    """FinShield AI API client with automatic retries and idempotency.
    
    Args:
        api_key: API key for authentication
        base_url: Base URL for the API (default: https://api.finshield.ai)
        timeout: Request timeout in seconds (default: 30)
        max_retries: Maximum number of retry attempts (default: 3)
        retry_delay: Initial delay between retries in seconds (default: 1)
    """
    
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.finshield.ai",
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: int = 1,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        self.client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": f"finshield-python-sdk/{self._get_version()}",
            },
        )
    
    def _get_version(self) -> str:
        """Get SDK version."""
        from . import __version__
        return __version__
    
    def _request(
        self,
        method: str,
        path: str,
        idempotency_key: Optional[str] = None,
        **kwargs: Any,
    ) -> dict:
        """Make HTTP request with retry logic.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            path: API path
            idempotency_key: Optional idempotency key for POST requests
            **kwargs: Additional arguments passed to httpx.request
        
        Returns:
            Response JSON as dict
        
        Raises:
            FinShieldError: If request fails after all retries
        """
        headers = kwargs.pop("headers", {})
        
        # Add idempotency key for POST requests if not provided
        if method.upper() == "POST" and idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                response = self.client.request(method, path, headers=headers, **kwargs)
                
                # Success
                if response.is_success:
                    return response.json()
                
                # Client errors (4xx) - don't retry
                if response.status_code in (400, 401, 403, 404, 422):
                    error_body = response.json() if response.content else {}
                    error_msg = error_body.get("detail", response.text)
                    
                    if response.status_code == 401:
                        raise AuthenticationError(error_msg, status_code=401, response_body=error_body)
                    elif response.status_code == 404:
                        raise NotFoundError(error_msg, status_code=404, response_body=error_body)
                    elif response.status_code == 422:
                        raise ValidationError(error_msg, status_code=422, response_body=error_body)
                    else:
                        raise FinShieldError(error_msg, status_code=response.status_code, response_body=error_body)
                
                # Rate limit (429) - retry with backoff
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", self.retry_delay * (attempt + 1)))
                    if attempt < self.max_retries - 1:
                        time.sleep(retry_after)
                        continue
                    raise RateLimitError(
                        "Rate limit exceeded",
                        retry_after=retry_after,
                        status_code=429,
                        response_body=response.json() if response.content else {},
                    )
                
                # Server errors (5xx) - retry
                if response.status_code >= 500:
                    last_exception = ServerError(
                        f"Server error: {response.status_code}",
                        status_code=response.status_code,
                        response_body=response.json() if response.content else {},
                    )
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay * (2 ** attempt))  # Exponential backoff
                        continue
                
                # Other errors - don't retry
                raise FinShieldError(
                    f"Request failed: {response.status_code}",
                    status_code=response.status_code,
                    response_body=response.json() if response.content else {},
                )
            
            except httpx.RequestError as e:
                last_exception = FinShieldError(f"Request error: {str(e)}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))
                    continue
        
        # All retries exhausted
        raise last_exception or FinShieldError("Request failed after all retries")
    
    def _generate_idempotency_key(self) -> str:
        """Generate a unique idempotency key."""
        return str(uuid.uuid4())
    
    # ── Health ──
    
    def health(self) -> HealthData:
        """Check API health."""
        data = self._request("GET", "/api/health")
        return HealthData(**data)
    
    # ── Authentication ──
    
    def login(self, email: str, password: str) -> dict:
        """Authenticate and get access token."""
        return self._request("POST", "/api/auth/login", json={"email": email, "password": password})
    
    def me(self) -> UserProfile:
        """Get current user profile."""
        data = self._request("GET", "/api/auth/me")
        return UserProfile(**data)
    
    # ── Transactions ──
    
    def screen_transaction(
        self,
        sender_name: str,
        receiver_name: str,
        amount: float,
        currency: str,
        transaction_type: str = "wire",
        idempotency_key: Optional[str] = None,
        **kwargs: Any,
    ) -> TransactionResponse:
        """Screen a transaction for compliance.
        
        Args:
            sender_name: Name of the sender
            receiver_name: Name of the receiver
            amount: Transaction amount
            currency: Currency code (e.g., USD, EUR)
            transaction_type: Type of transaction (wire, ach, card, etc.)
            idempotency_key: Optional idempotency key (auto-generated if not provided)
            **kwargs: Additional transaction fields
        
        Returns:
            TransactionResponse with screening result
        """
        if idempotency_key is None:
            idempotency_key = self._generate_idempotency_key()
        
        payload = {
            "sender_name": sender_name,
            "receiver_name": receiver_name,
            "amount": amount,
            "currency": currency,
            "transaction_type": transaction_type,
            "idempotency_key": idempotency_key,
            **kwargs,
        }
        
        data = self._request("POST", "/api/v1/transactions", idempotency_key=idempotency_key, json=payload)
        
        if data.get("data"):
            data["data"] = ScreeningResult(**data["data"])
        
        return TransactionResponse(**data)
    
    def list_transactions(self, limit: int = 50, offset: int = 0) -> list[dict]:
        """List transactions."""
        return self._request("GET", f"/api/v1/transactions?limit={limit}&offset={offset}")
    
    def get_transaction(self, transaction_id: str) -> dict:
        """Get transaction details."""
        return self._request("GET", f"/api/v1/transactions/{transaction_id}")
    
    # ── Cases ──
    
    def list_cases(self) -> list[CaseData]:
        """List all cases."""
        data = self._request("GET", "/api/v1/cases")
        return [CaseData(**case) for case in data]
    
    def get_case(self, case_id: str) -> CaseData:
        """Get case details."""
        data = self._request("GET", f"/api/v1/cases/{case_id}")
        return CaseData(**data)
    
    def create_case(self, transaction_id: str, reason: str, priority: str = "medium") -> CaseData:
        """Create a new case."""
        data = self._request(
            "POST",
            "/api/v1/cases",
            json={"transaction_id": transaction_id, "reason": reason, "priority": priority},
        )
        return CaseData(**data)
    
    # ── Rules ──
    
    def list_rules(self) -> list[RuleDefinition]:
        """List all rules."""
        data = self._request("GET", "/api/v1/rules")
        return [RuleDefinition(**rule) for rule in data]
    
    # ── Credits ──
    
    def get_credits(self) -> CreditsData:
        """Get credit balance."""
        data = self._request("GET", "/api/v1/credits")
        return CreditsData(**data)
    
    # ── Stats ──
    
    def get_stats(self) -> StatsData:
        """Get dashboard statistics."""
        data = self._request("GET", "/api/v1/stats")
        return StatsData(**data)
    
    def close(self):
        """Close the HTTP client."""
        self.client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
