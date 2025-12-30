# Phase 1: Meta Setup & Secrets

**Status:** Ready
**Dependencies:** None (parallel task)
**Output:** Modal secrets configured, test number available

## Overview

Manual setup of Meta Developer infrastructure. Can proceed in parallel with code implementation.

## Tasks

### 1.1 Create Meta Developer Account

1. Go to https://developers.facebook.com/
2. Create account or log in with Facebook
3. Verify email

### 1.2 Create WhatsApp Business App

1. Go to https://developers.facebook.com/apps/
2. Click "Create App"
3. Select "Business" as app type
4. Enter app name (e.g., "Claude Agents")
5. Select business portfolio (or create one)
6. Add WhatsApp product to app

### 1.3 Configure Test Number

1. In App Dashboard → WhatsApp → API Setup
2. Note the "Test Phone Number" and "Phone Number ID"
3. Add your personal number to "To" recipients
4. Send test message to verify setup works

### 1.4 Generate Access Token

**Option A: Temporary Token (development)**
- Use the 24-hour token shown in API Setup
- Good for initial testing

**Option B: Permanent System User Token (production)**
1. Go to Business Settings → System Users
2. Create system user with admin role
3. Add WhatsApp app to system user
4. Generate token with permissions:
   - `whatsapp_business_messaging`
   - `whatsapp_business_management`

### 1.5 Get App Secret

1. Go to App Dashboard → Settings → Basic
2. Copy "App Secret" (for webhook signature validation)

### 1.6 Create Modal Secrets

```bash
# Create webhook verify token (any random string)
VERIFY_TOKEN=$(openssl rand -hex 16)

modal secret create whatsapp-credentials \
  WHATSAPP_TOKEN="<access_token_from_step_1.4>" \
  WHATSAPP_PHONE_ID="<phone_number_id_from_step_1.3>" \
  WHATSAPP_BUSINESS_ID="<business_account_id>" \
  WHATSAPP_APP_SECRET="<app_secret_from_step_1.5>" \
  WHATSAPP_VERIFY_TOKEN="$VERIFY_TOKEN"

echo "Save this verify token for webhook config: $VERIFY_TOKEN"
```

### 1.7 Update Modal App Secrets

In `main.py`, add to secrets list:
```python
secrets = [
    ...existing secrets...
    modal.Secret.from_name("whatsapp-credentials"),
]
```

## Verification

- [ ] Meta Developer account created
- [ ] WhatsApp Business app created
- [ ] Test number available
- [ ] Access token generated
- [ ] Modal secrets created
- [ ] Test message sent successfully

## Notes

- Business verification for production: Submit business documents via Business Settings
- Verification can take 2-7 business days
- Test number has 1000 messages/day limit
- For production: add dedicated phone number (must not be on WhatsApp already)
