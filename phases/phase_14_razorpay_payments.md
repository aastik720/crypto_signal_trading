PROMPT FOR PHASE 11:

PROJECT: CryptoSignal Bot
PHASE: 11 - Razorpay Payment Integration

Create file: payments/razorpay.py

PURPOSE:
Handle payment processing using Razorpay.
Generate payment links, verify payments, activate subscriptions.

RAZORPAY SETUP:
- Use razorpay Python SDK
- API Key and Secret from .env file
- All amounts in PAISE (₹999 = 99900 paise)

CLASS: PaymentManager

ATTRIBUTES:
- client: razorpay.Client instance
- subscription_price: 99900 (paise)
- currency: "INR"

METHODS:

1. __init__(self)
   - Initialize Razorpay client with key_id and key_secret
   - from config.settings import RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET
   - client = razorpay.Client(auth=(key_id, key_secret))

2. create_payment_link(self, chat_id: int, username: str) -> str
   - Create a Razorpay payment link for the user
   
   Method using Razorpay Payment Links API:
   
   payment_link_data = {
       "amount": 99900,  # ₹999 in paise
       "currency": "INR",
       "description": "CryptoSignal Bot - 28 Days Premium",
       "customer": {
           "name": username or "User",
           "contact": "",  # optional
           "email": ""     # optional
       },
       "notify": {
           "sms": False,
           "email": False
       },
       "reminder_enable": False,
       "notes": {
           "chat_id": str(chat_id),
           "plan": "28_days_premium"
       },
       "callback_url": "",  # We'll use webhook instead
       "callback_method": "get"
   }
   
   response = client.payment_link.create(payment_link_data)
   payment_link_url = response["short_url"]
   order_id = response["id"]
   
   - Save to database: create_payment_record(chat_id, order_id, amount)
   - Return payment_link_url

   ALTERNATIVE METHOD (Razorpay Orders):
   If payment links don't work well, use Orders API:
   
   order_data = {
       "amount": 99900,
       "currency": "INR",
       "receipt": f"order_{chat_id}_{timestamp}",
       "notes": {
           "chat_id": str(chat_id)
       }
   }
   order = client.order.create(data=order_data)
   
   Then create a hosted checkout page URL.

3. verify_payment(self, payment_id: str, order_id: str, signature: str) -> bool
   - Verify payment signature using Razorpay utility
   - params = {
       "razorpay_order_id": order_id,
       "razorpay_payment_id": payment_id,
       "razorpay_signature": signature
     }
   - client.utility.verify_payment_signature(params)
   - Returns True if valid, False if invalid

4. async check_payment_status(self, order_id: str) -> str
   - Fetch payment link/order status from Razorpay
   - payment_link = client.payment_link.fetch(order_id)
   - Return status: "created" / "paid" / "expired" / "cancelled"

5. async poll_payment_status(self, chat_id: int, order_id: str)
   - Since Telegram bot can't receive webhooks easily,
     we POLL Razorpay every 30 seconds to check if payment is done
   - Maximum polling time: 30 minutes
   - Every 30 seconds:
     - Check payment status
     - If "paid":
       - Generate unique token
       - Activate subscription in database
       - Send success message to user
       - Send notification to admin
       - Stop polling
     - If still "created":
       - Continue polling
     - If "expired" or "cancelled":
       - Send failure message to user
       - Stop polling

6. generate_token(self, chat_id: int) -> str
   - Generate a unique subscription token
   - Format: "CSB-{random_8_chars}-{chat_id_last4}"
   - Example: "CSB-A7F3K9M2-1234"
   - Use secrets.token_hex() for randomness
   - Must be unique (check database)
   - Lock token to chat_id in database
   - Return token string

7. async handle_successful_payment(self, chat_id: int, payment_id: str, order_id: str)
   - Called when payment is confirmed
   - Step 1: Generate unique token
   - Step 2: Activate subscription (28 days from now)
   - Step 3: Lock token to chat_id
   - Step 4: Update payment record in database
   - Step 5: Send message to user:
     "✅ Payment Successful!
      
      🎉 Your premium access is now active!
      
      📅 Valid until: DD/MM/YYYY
      🔑 Your token: CSB-XXXXXXXX-XXXX
      🔒 Locked to your account
      
      You will now receive all trading signals
      in the private channel: @ChannelLink
      
      Enjoy your premium experience! 🚀"
   
   - Step 6: Add user to private channel (if possible)
   - Step 7: Send admin notification about new payment

WEBHOOK ALTERNATIVE:
If deploying on a server with public URL:
- Set up /webhook endpoint
- Razorpay sends POST request on payment completion
- Verify webhook signature
- Process payment
- This is more reliable than polling

IMPORTANT:
- NEVER store Razorpay keys in code, always use .env
- Always verify payment signature before activating
- Handle duplicate payment attempts
- Handle network errors with Razorpay API
- Log all payment activities
- Amount must be in PAISE for Razorpay
- Test with Razorpay TEST keys first