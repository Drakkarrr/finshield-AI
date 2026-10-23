# API Key Management

<cite>
**Referenced Files in This Document**   
- [main.py](file://backend/app/main.py)
- [auth.py](file://backend/app/auth.py)
- [db_models.py](file://backend/app/db_models.py)
- [api.ts](file://platform-app/src/lib/api.ts)
- [page.tsx](file://platform-app/src/app/api-keys/page.tsx)
</cite>

## Table of Contents
1. [Introduction](#introduction)
2. [Project Structure](#project-structure)
3. [Core Components](#core-components)
4. [Architecture Overview](#architecture-overview)
5. [Detailed Component Analysis](#detailed-component-analysis)
6. [Dependency Analysis](#dependency-analysis)
7. [Performance Considerations](#performance-considerations)
8. [Troubleshooting Guide](#troubleshooting-guide)
9. [Conclusion](#conclusion)

## Introduction
This document describes the API key management functionality exposed by the FinShield backend. It covers the complete lifecycle of programmatic API keys: creation, listing, and revocation. It also explains how authentication works for these endpoints, how secure keys are generated and stored, and how clients should handle the one-time full-key response.

The implementation is built with FastAPI, SQLAlchemy ORM models, bcrypt-based hashing, and JWT bearer authentication. The Next.js dashboard provides a user interface for creating, viewing, copying, and revoking API keys.

## Project Structure
The API key management feature spans three main areas:

- Backend API routes and request/response schemas: `backend/app/main.py`
- Authentication, API key generation, and live API key verification: `backend/app/auth.py`
- Database schema for users and API keys: `backend/app/db_models.py`
- Frontend API client and dashboard page: `platform-app/src/lib/api.ts`, `platform-app/src/app/api-keys/page.tsx`

```mermaid
graph TB
Client["Client or Dashboard"] --> Routes["FastAPI Routes<br/>/api/v1/keys"]
Routes --> Auth["Authentication Dependency<br/>get_current_user()"]
Auth --> DBModel["ApiKey ORM Model"]
Routes --> DBModel
Routes --> Store["Database Session"]
Client --> Frontend["Next.js Dashboard<br/>/src/app/api-keys/page.tsx"]
Frontend --> ApiClient["Frontend API Client<br/>/src/lib/api.ts"]
ApiClient --> Routes
```

**Diagram sources**
- [main.py:350-427](file://backend/app/main.py#L350-L427)
- [auth.py:59-121](file://backend/app/auth.py#L59-L121)
- [db_models.py:59-72](file://backend/app/db_models.py#L59-L72)
- [api.ts:561-573](file://platform-app/src/lib/api.ts#L561-L573)
- [page.tsx:8-56](file://platform-app/src/app/api-keys/page.tsx#L8-L56)

**Section sources**
- [main.py:350-427](file://backend/app/main.py#L350-L427)
- [auth.py:59-121](file://backend/app/auth.py#L59-L121)
- [db_models.py:59-72](file://backend/app/db_models.py#L59-L72)
- [api.ts:561-573](file://platform-app/src/lib/api.ts#L561-L573)
- [page.tsx:8-56](file://platform-app/src/app/api-keys/page.tsx#L8-L56)

## Core Components
The API key management system consists of:

| Component | Responsibility |
|---|---|
| `ApiKeyCreateRequest` | Request body for creating an API key; requires a descriptive name. |
| `ApiKeyResponse` | Response model for listing API keys; includes identifier, name, masked prefix, active state, creation time, and last-used timestamp. |
| `create_api_key()` | Generates a secure key, stores only its hash and prefix, and returns the full key once during creation. |
| `list_api_keys()` | Returns all API keys belonging to the authenticated user with masked prefixes. |
| `revoke_api_key()` | Deactivates an API key by setting it inactive. |
| `generate_api_key()` | Produces a random secret prefixed with `fsk_live_`, hashes it with bcrypt, and derives a display-safe prefix. |
| `get_current_user()` | Accepts either a JWT bearer token or a live API key starting with `fsk_`. |
| `ApiKey` ORM model | Persists user-scoped API keys, their hashed secrets, display prefixes, active state, and usage metadata. |

**Section sources**
- [main.py:354-427](file://backend/app/main.py#L354-L427)
- [auth.py:59-121](file://backend/app/auth.py#L59-L121)
- [db_models.py:59-72](file://backend/app/db_models.py#L59-L72)

## Architecture Overview
The API key lifecycle follows this flow:

1. A client authenticates using a JWT bearer token from `/api/auth/login` or `/api/auth/register`.
2. The client calls `POST /api/v1/keys` with a descriptive key name.
3. The backend generates a cryptographically secure raw key, hashes it, stores only the hash and a masked prefix, and returns the full key exactly once.
4. Clients store the returned full key securely.
5. Clients can call `GET /api/v1/keys` to list keys with masked prefixes and activity metadata.
6. Clients can call `DELETE /api/v1/keys/{key_id}` to revoke a key.
7. When a live API key is used as the `Authorization: Bearer fsk_...` value, the backend verifies it against the stored hash and updates `last_used_at`.

```mermaid
sequenceDiagram
participant Client as "Client"
participant Dashboard as "Next.js Dashboard"
participant API as "FastAPI /api/v1/keys"
participant Auth as "get_current_user()"
participant DB as "Database"
Client->>Dashboard : Create API key with name
Dashboard->>API : POST /api/v1/keys {name}
API->>Auth : Validate JWT bearer token
Auth-->>API : Current user
API->>DB : Insert ApiKey with hashed secret and prefix
DB-->>API : Persisted key record
API-->>Dashboard : Full key + id + name + key_prefix + created_at
Dashboard-->>Client : Display one-time full key
Client->>API : GET /api/v1/keys
API->>Auth : Validate JWT bearer token
Auth-->>API : Current user
API->>DB : Query ApiKey rows for user
DB-->>API : Masked key records
API-->>Client : List of ApiKeyResponse objects
Client->>API : DELETE /api/v1/keys/{key_id}
API->>Auth : Validate JWT bearer token
Auth-->>API : Current user
API->>DB : Set is_active = False
DB-->>API : Success
API-->>Client : {detail : "API key revoked"}
```

**Diagram sources**
- [main.py:366-427](file://backend/app/main.py#L366-L427)
- [auth.py:59-121](file://backend/app/auth.py#L59-L121)
- [db_models.py:59-72](file://backend/app/db_models.py#L59-L72)
- [api.ts:561-573](file://platform-app/src/lib/api.ts#L561-L573)
- [page.tsx:32-56](file://platform-app/src/app/api-keys/page.tsx#L32-L56)

## Detailed Component Analysis

### Authentication Model
All API key management endpoints require authentication through the `get_current_user()` dependency. This dependency supports two authentication paths:

| Path | Authorization header | Behavior |
|---|---|---|
| JWT bearer token | `Authorization: Bearer <jwt>` | Decodes the JWT, resolves the user, checks account status. |
| Live API key | `Authorization: Bearer fsk_<prefix_and_secret>` | Filters candidates by the first 12 characters, verifies the full secret with bcrypt, updates `last_used_at`, and resolves the owning user. |

If no credentials are provided, the endpoint returns `401 Unauthorized`. If credentials are invalid or expired, it also returns `401 Unauthorized`. If the owning user is disabled, it returns `403 Forbidden`.

```mermaid
flowchart TD
Start(["Request arrives"]) --> HasCreds{"Has Authorization header?"}
HasCreds --> |No| NoAuth["Return 401 Not authenticated"]
HasCreds --> |Yes| IsApiKey{"Token starts with fsk_?"}
IsApiKey --> |Yes| FindCandidates["Find ApiKey rows matching key_prefix and is_active"]
FindCandidates --> VerifyHash["Verify full secret against stored hash"]
VerifyHash --> Verified{"Verified?"}
Verified --> |No| InvalidKey["Return 401 Invalid API key"]
Verified --> |Yes| LoadUser["Load owning User"]
LoadUser --> Active{"User is active?"}
Active --> |No| Disabled["Return 403 Account disabled"]
Active --> |Yes| UpdateUsed["Set last_used_at and commit"]
UpdateUsed --> ReturnUser["Return current user"]
IsApiKey --> |No| DecodeJWT["Decode JWT"]
DecodeJWT --> ValidJWT{"Valid payload?"}
ValidJWT --> |No| BadJWT["Return 401 Invalid or expired token"]
ValidJWT --> LoadUserById["Load User by sub"]
LoadUserById --> CheckActive{"User is active?"}
CheckActive --> |No| Disabled
CheckActive --> |Yes| ReturnUser
```

**Diagram sources**
- [auth.py:59-113](file://backend/app/auth.py#L59-L113)

**Section sources**
- [auth.py:59-121](file://backend/app/auth.py#L59-L121)

### Secure Key Generation and Storage
The `generate_api_key()` function implements the secure key lifecycle:

1. Generate a random URL-safe secret.
2. Prefix it with `fsk_live_`.
3. Hash the full raw key using bcrypt.
4. Derive a display-safe prefix by taking the first 12 characters and appending `...`.
5. Return the tuple `(raw_key, key_hash, key_prefix)`.

Only the bcrypt hash and the masked prefix are persisted. The raw key is never stored after creation.

```mermaid
flowchart TD
Entry(["generate_api_key()"]) --> Random["Generate random secret"]
Random --> Prefix["Prepend fsk_live_"]
Prefix --> Hash["Hash full key with bcrypt"]
Hash --> Mask["Derive key_prefix from first 12 chars + ..."]
Mask --> Return["Return (raw_key, key_hash, key_prefix)"]
```

**Diagram sources**
- [auth.py:116-121](file://backend/app/auth.py#L116-L121)

**Section sources**
- [auth.py:116-121](file://backend/app/auth.py#L116-L121)

### Data Model
The `ApiKey` table stores user-scoped API key metadata:

| Column | Type | Purpose |
|---|---|---|
| `id` | String primary key | Internal database identifier for the key record. |
| `user_id` | String foreign key | Links the key to the owning user. |
| `name` | String | Human-readable label such as Production or Staging. |
| `key_hash` | String unique column | bcrypt hash of the full raw API key. |
| `key_prefix` | String | Masked prefix used for identification. |
| `is_active` | Boolean | Whether the key can authenticate requests. |
| `created_at` | DateTime | Creation timestamp. |
| `last_used_at` | Nullable DateTime | Timestamp updated when the live API key authenticates a request. |

```mermaid
erDiagram
USER ||--o{ API_KEYS : owns
API_KEYS {
string id PK
string user_id FK
string name
string key_hash UK
string key_prefix
boolean is_active
datetime created_at
datetime last_used_at
}
```

**Diagram sources**
- [db_models.py:22-72](file://backend/app/db_models.py#L22-L72)

**Section sources**
- [db_models.py:59-72](file://backend/app/db_models.py#L59-L72)

### Endpoint: Create API Key
- **HTTP method:** `POST`
- **Path:** `/api/v1/keys`
- **Status code on success:** `201 Created`
- **Authentication:** Required via JWT bearer token or live API key.
- **Request body:** `ApiKeyCreateRequest`
  - `name`: String describing the key.
- **Success response:** Object containing:
  - `id`: Database key record identifier.
  - `name`: Provided key name.
  - `key`: Full raw API key. This field is only present on creation.
  - `key_prefix`: Masked prefix for identification.
  - `created_at`: ISO-formatted creation timestamp.
- **Error responses:**
  - `401 Unauthorized`: Missing, invalid, or expired credentials.
  - `422 Unprocessable Entity`: Invalid request body.
  - `500 Internal Server Error`: Unexpected server error.

Practical curl example for creation:

```bash
curl -X POST http://localhost:8091/api/v1/keys \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Production Service"}'
```

Expected successful response shape:

```json
{
  "id": "string",
  "name": "Production Service",
  "key": "fsk_live_random_secret",
  "key_prefix": "fsk_live_xxx...",
  "created_at": "YYYY-MM-DDTHH:MM:SS"
}
```

Security note: Copy the full `key` value immediately. It will not be returned again by subsequent listing or lookup operations.

**Section sources**
- [main.py:354-393](file://backend/app/main.py#L354-L393)
- [auth.py:116-121](file://backend/app/auth.py#L116-L121)

### Endpoint: List API Keys
- **HTTP method:** `GET`
- **Path:** `/api/v1/keys`
- **Status code on success:** `200 OK`
- **Authentication:** Required via JWT bearer token or live API key.
- **Query parameters:** None.
- **Success response:** Array of `ApiKeyResponse` objects:
  - `id`: Database key record identifier.
  - `name`: Human-readable key label.
  - `key_prefix`: Masked prefix for identification.
  - `is_active`: Boolean indicating whether the key is active.
  - `created_at`: ISO-formatted creation timestamp.
  - `last_used_at`: Nullable ISO-formatted timestamp updated when the live API key authenticates a request.
- **Error responses:**
  - `401 Unauthorized`: Missing, invalid, or expired credentials.
  - `500 Internal Server Error`: Unexpected server error.

Practical curl example for listing:

```bash
curl -X GET http://localhost:8091/api/v1/keys \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

Expected successful response shape:

```json
[
  {
    "id": "string",
    "name": "Production Service",
    "key_prefix": "fsk_live_xxx...",
    "is_active": true,
    "created_at": "YYYY-MM-DDTHH:MM:SS",
    "last_used_at": "YYYY-MM-DDTHH:MM:SS"
  },
  {
    "id": "string",
    "name": "Staging Service",
    "key_prefix": "fsk_live_yyy...",
    "is_active": false,
    "created_at": "YYYY-MM-DDTHH:MM:SS",
    "last_used_at": null
  }
]
```

Note: The current implementation does not provide filtering by active status or prefix masking beyond what is already stored in `key_prefix`. To list only active keys, filter the returned array on the client side.

**Section sources**
- [main.py:396-409](file://backend/app/main.py#L396-L409)
- [db_models.py:59-72](file://backend/app/db_models.py#L59-L72)

### Endpoint: Revoke API Key
- **HTTP method:** `DELETE`
- **Path:** `/api/v1/keys/{key_id}`
- **Status code on success:** `200 OK`
- **Authentication:** Required via JWT bearer token or live API key.
- **Path parameter:**
  - `key_id`: Database identifier of the API key record to revoke.
- **Success response:**
  - `detail`: Confirmation message.
- **Error responses:**
  - `401 Unauthorized`: Missing, invalid, or expired credentials.
  - `404 Not Found`: The key ID does not belong to the authenticated user or does not exist.
  - `500 Internal Server Error`: Unexpected server error.

Practical curl example for revocation:

```bash
curl -X DELETE http://localhost:8091/api/v1/keys/YOUR_KEY_RECORD_ID \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

Expected successful response shape:

```json
{
  "detail": "API key revoked"
}
```

Revocation sets `is_active` to `false`. It does not delete the record, so audit history remains available.

**Section sources**
- [main.py:412-427](file://backend/app/main.py#L412-L427)

### Using a Live API Key
A live API key can authenticate any protected endpoint, including transaction screening. The expected format is:

```
Authorization: Bearer fsk_live_random_secret
```

When verified successfully, the backend:

1. Matches the first 12 characters as the key prefix.
2. Verifies the full secret against the stored bcrypt hash.
3. Updates `last_used_at` on the matching `ApiKey` row.
4. Resolves the owning user.
5. Rejects the request if the owning user is disabled.

Practical curl example using a live API key:

```bash
curl -X POST http://localhost:8091/api/v1/transactions \
  -H "Authorization: Bearer fsk_live_YOUR_FULL_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 1000,
    "currency": "USD",
    "transaction_type": "wire",
    "sender_name": "Alice",
    "receiver_name": "Bob",
    "destination_country": "US"
  }'
```

**Section sources**
- [auth.py:76-92](file://backend/app/auth.py#L76-L92)

### Frontend Integration
The Next.js dashboard exposes an API keys page that:

- Loads the current user’s API keys.
- Creates new keys by calling `POST /api/v1/keys`.
- Displays the one-time full key and warns that it must be copied immediately.
- Lists existing keys with active/revoked status.
- Revokes keys by calling `DELETE /api/v1/keys/{key_id}`.
- Uses the shared frontend API client to attach the JWT bearer token.

```mermaid
sequenceDiagram
participant UI as "ApiKeysPage"
participant Client as "api.ts client"
participant API as "FastAPI /api/v1/keys"
UI->>Client : listApiKeys()
Client->>API : GET /api/v1/keys
API-->>Client : ApiKeyData[]
Client-->>UI : Keys list
UI->>Client : createApiKey(name)
Client->>API : POST /api/v1/keys
API-->>Client : ApiKeyData with full key
Client-->>UI : Newly created key
UI->>Client : revokeApiKey(id)
Client->>API : DELETE /api/v1/keys/id
API-->>Client : {detail}
Client-->>UI : Updated key list
```

**Diagram sources**
- [page.tsx:8-56](file://platform-app/src/app/api-keys/page.tsx#L8-L56)
- [api.ts:561-573](file://platform-app/src/lib/api.ts#L561-L573)
- [main.py:366-427](file://backend/app/main.py#L366-L427)

**Section sources**
- [page.tsx:8-56](file://platform-app/src/app/api-keys/page.tsx#L8-L56)
- [api.ts:347-355](file://platform-app/src/lib/api.ts#L347-L355)
- [api.ts:561-573](file://platform-app/src/lib/api.ts#L561-L573)

## Dependency Analysis
The API key management endpoints depend on several components:

```mermaid
graph LR
CreateRoute["POST /api/v1/keys"] --> GetCurrentUser["get_current_user()"]
ListRoute["GET /api/v1/keys"] --> GetCurrentUser
RevokeRoute["DELETE /api/v1/keys/{key_id}"] --> GetCurrentUser
CreateRoute --> GenerateKey["generate_api_key()"]
CreateRoute --> ApiKeyModel["ApiKey ORM"]
ListRoute --> ApiKeyModel
RevokeRoute --> ApiKeyModel
GetCurrentUser --> ApiKeyModel
GetCurrentUser --> UserModel["User ORM"]
```

**Diagram sources**
- [main.py:366-427](file://backend/app/main.py#L366-L427)
- [auth.py:59-121](file://backend/app/auth.py#L59-L121)
- [db_models.py:22-72](file://backend/app/db_models.py#L22-L72)

Coupling and cohesion observations:

- Route handlers are cohesive around API key lifecycle operations.
- Authentication logic is centralized in `get_current_user()`, supporting both JWT and live API key flows.
- Key generation is isolated in `generate_api_key()`, making security policy changes easier to locate.
- The `ApiKey` model is the single source of truth for persistence and is referenced by both route handlers and authentication.

Potential risks:

- The revoke endpoint does not return the revoked key object; callers must track state locally or refresh the list.
- Listing does not include server-side filtering by active status, so clients must filter results if they need only active keys.
- `last_used_at` is updated only when a live API key authenticates; it is not updated for JWT-based dashboard requests.

**Section sources**
- [main.py:366-427](file://backend/app/main.py#L366-L427)
- [auth.py:59-121](file://backend/app/auth.py#L59-L121)
- [db_models.py:59-72](file://backend/app/db_models.py#L59-L72)

## Performance Considerations
- Key creation performs one bcrypt hash operation and one database insert.
- Listing keys performs a simple user-scoped query and constructs Pydantic response objects.
- Revocation performs a user-scoped lookup and a single boolean update.
- Live API key authentication performs a prefix-filtered query followed by bcrypt verification; this is intentionally more expensive than JWT decoding but limits candidate rows by prefix.
- Rate limiting applies globally through the SlowAPI limiter, which may affect API key management endpoints under heavy load.

Recommendations:

- Cache or precompute active key lists at the client level if frequently accessed.
- Monitor bcrypt verification latency under high concurrency.
- Add database indexes if key lookups become a bottleneck in large deployments.

[No sources needed since this section provides general guidance]

## Troubleshooting Guide

| Symptom | Likely Cause | Resolution |
|---|---|---|
| `401 Not authenticated` | Missing `Authorization` header. | Include `Authorization: Bearer YOUR_JWT_TOKEN` or a live API key. |
| `401 Invalid or expired token` | JWT is malformed or expired. | Re-authenticate and obtain a fresh token. |
| `401 Invalid API key` | Live API key prefix does not match or secret does not verify. | Confirm the full key was copied immediately after creation. |
| `403 Account disabled` | Owning user is inactive. | Reactivate the user account before using the key. |
| `404 API key not found` | Revocation requested for a key ID that does not belong to the authenticated user. | Use the correct `id` from the listing response. |
| `422 Invalid request data` | Missing or invalid request body. | Ensure `name` is provided for key creation. |
| `429 Rate limit exceeded` | Too many requests from the same IP. | Retry later or reduce request frequency. |
| `500 Internal server error` | Unexpected server failure. | Check server logs and retry after recovery. |

Common debugging steps:

1. Verify the JWT bearer token by calling `/api/auth/me`.
2. Confirm the live API key format starts with `fsk_`.
3. Compare the requested `key_id` with the `id` field from `GET /api/v1/keys`.
4. Inspect the dashboard’s local storage token if the Next.js client fails to attach authorization.
5. Review backend logs for authentication failures and database errors.

**Section sources**
- [auth.py:59-113](file://backend/app/auth.py#L59-L113)
- [main.py:81-115](file://backend/app/main.py#L81-L115)
- [main.py:412-427](file://backend/app/main.py#L412-L427)

## Conclusion
The FinShield API key management system provides a secure, user-scoped mechanism for programmatic access. Keys are generated with cryptographic randomness, stored only as bcrypt hashes, and identified by masked prefixes. The full key is returned exactly once during creation, reducing exposure risk. Authentication supports both JWT bearer tokens for interactive use and live API keys for machine-to-machine workflows. The Next.js dashboard offers a practical interface for managing keys, while the backend enforces consistent security and persistence rules.

[No sources needed since this section summarizes without analyzing specific files]