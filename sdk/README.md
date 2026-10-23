# FinShield AI Python SDK

Official Python SDK for the FinShield AI transaction compliance API.

## Installation

```bash
pip install finshield-sdk
```

## Quick Start

```python
from finshield_sdk import FinShieldClient

# Initialize client
client = FinShieldClient(
    api_key="your-api-key",
    base_url="https://api.finshield.ai"
)

# Screen a transaction
result = client.screen_transaction(
    sender_name="John Doe",
    receiver_name="Jane Smith",
    amount=10000.0,
    currency="USD",
    transaction_type="wire"
)

print(f"Status: {result.data.status}")
print(f"Risk Score: {result.data.risk_score}")
print(f"Credits Used: {result.data.credits_consumed}")
```

## Features

- **Type-safe**: Full type hints for all models and methods
- **Automatic retries**: Exponential backoff for transient errors
- **Idempotency**: Automatic idempotency key generation for POST requests
- **Rate limiting**: Automatic handling of 429 responses with Retry-After
- **Error handling**: Specific exception types for different error scenarios

## Usage Examples

### Authentication

```python
# Login and get token
auth = client.login("user@example.com", "password")
print(f"Token: {auth['access_token']}")

# Get current user
user = client.me()
print(f"User: {user.email}, Plan: {user.plan}")
```

### Transaction Screening

```python
# Screen with custom idempotency key
result = client.screen_transaction(
    sender_name="Acme Corp",
    receiver_name="Supplier Ltd",
    amount=50000.0,
    currency="USD",
    transaction_type="wire",
    destination_country="US",
    idempotency_key="unique-key-123"  # Optional
)

if result.success:
    print(f"Transaction {result.data.transaction_id}: {result.data.status}")
else:
    print(f"Error: {result.error}")
```

### Case Management

```python
# List cases
cases = client.list_cases()
for case in cases:
    print(f"Case {case.case_id}: {case.status} ({case.priority})")

# Create case
case = client.create_case(
    transaction_id="tx-123",
    reason="Suspicious activity detected",
    priority="high"
)
```

### Credits and Stats

```python
# Get credit balance
credits = client.get_credits()
print(f"Remaining: {credits.remaining_credits}/{credits.total_credits}")

# Get dashboard stats
stats = client.get_stats()
print(f"Total screened: {stats.total_transactions}")
print(f"Flagged: {stats.flagged}")
```

## Error Handling

```python
from finshield_sdk import (
    FinShieldClient,
    AuthenticationError,
    RateLimitError,
    ValidationError,
    ServerError,
)

client = FinShieldClient(api_key="your-key")

try:
    result = client.screen_transaction(...)
except AuthenticationError as e:
    print(f"Authentication failed: {e}")
except RateLimitError as e:
    print(f"Rate limited. Retry after {e.retry_after}s")
except ValidationError as e:
    print(f"Validation error: {e}")
except ServerError as e:
    print(f"Server error: {e}")
except FinShieldError as e:
    print(f"API error: {e}")
```

## Configuration

```python
client = FinShieldClient(
    api_key="your-key",
    base_url="https://api.finshield.ai",
    timeout=30,           # Request timeout in seconds
    max_retries=3,        # Maximum retry attempts
    retry_delay=1,        # Initial retry delay in seconds
)
```

## Idempotency

POST requests automatically include an idempotency key to prevent duplicate operations. You can provide your own key:

```python
result = client.screen_transaction(
    ...,
    idempotency_key="my-unique-key"
)
```

If you retry the same request with the same idempotency key, the API will return the original result instead of creating a duplicate.

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest
```

## License

MIT License - see LICENSE file for details.

## Support

- Documentation: https://docs.finshield.ai
- API Reference: https://api.finshield.ai/docs
- Support: support@finshield.ai
