PROMPT FOR PHASE 11:
====================

Project: CryptoSignal Bot (continuing from Phase 1-10)
Task: Build security system in security/auth.py

CONTEXT: Security is critical. Each token must be locked to 
ONE chat ID. No sharing possible. No bypassing.

BUILD security/auth.py with these EXACT specifications:

CLASS: AuthManager

TOKEN FORMAT:
- UUID4 based: "CSB-" + uuid4 (e.g., "CSB-a1b2c3d4-e5f6...")
- Always starts with "CSB-" prefix
- Total length: ~40 characters
- Unique every time

FUNCTIONS:

1. __init__(self)
   - Initialize database connection
   - Load Config

2. generate_token(self)
   - Create unique token with "CSB-" prefix
   - Verify it doesn't already exist in database
   - Return token string

3. async create_subscription(self, chat_id, payment_id="FAKE")
   - Generate new token
   - Calculate expiry date (today + 28 days)
   - Save to database:
     * token
     * chat_id (locked)
     * activation_date = now
     * expiry_date = now + 28 days
     * payment_id
     * is_active = True
   - Return: {
       "token": token,
       "expiry_date": expiry_date,
       "chat_id": chat_id
     }

4. async validate_token(self, token, chat_id)
   - Check 1: Does token exist? → "INVALID_TOKEN"
   - Check 2: Is token locked to different chat_id? → "LOCKED"
   - Check 3: Is token expired? → "EXPIRED"
   - Check 4: Is token already active? → If same chat_id, OK
   - If all pass: Return "VALID"
   - Return: {
       "status": "VALID"/"INVALID_TOKEN"/"LOCKED"/
         "EXPIRED"/"ERROR",
       "message": human-readable message,
       "expiry_date": date if valid
     }

5. async activate_token(self, token, chat_id)
   - Validate token first
   - If valid: lock to this chat_id permanently
   - Update database
   - Return success/failure

6. async is_authorized(self, chat_id)
   - Quick check: does this chat_id have active subscription?
   - Check expiry date
   - Return True/False

7. async check_and_expire(self)
   - Called periodically (every hour)
   - Find all users whose expiry_date has passed
   - Deactivate them
   - Return list of expired users (for notification)

8. async get_subscription_info(self, chat_id)
   - Return full subscription details for a user
   - Days remaining, token (masked), status, etc.

9. async revoke_token(self, token)
   - Admin function to revoke a token
   - Deactivate immediately

SECURITY RULES:
- Token CANNOT be unlocked from a chat_id once locked
- Same token CANNOT be activated on different chat_id
- No grace period after expiry
- Database-level enforcement (not just code-level)
- All validation functions must be fast (<100ms)
- Log all authentication attempts (success and failure)
- Log all suspicious activity (wrong token attempts)

ANTI-SHARING MEASURES:
- If someone tries to use a token already locked to another 
  chat_id, log this as "SHARING_ATTEMPT"
- After 3 sharing attempts from same chat_id, flag user
- Store sharing attempts in database

Full working code with all imports. Production-ready.