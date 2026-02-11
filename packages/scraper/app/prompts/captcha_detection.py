CAPTCHA_DETECTION_PROMPT = """
Analyze the following HTML snippet and determine if it contains a CAPTCHA challenge.

Look for:
1. Google reCAPTCHA (v2/v3) - iframes with src containing "recaptcha", divs with class "g-recaptcha"
2. hCaptcha - iframes/divs with "hcaptcha" references
3. Cloudflare Turnstile - divs with "cf-turnstile" class
4. Custom CAPTCHAs - image challenges, math puzzles, text verification
5. 2FA prompts - OTP input fields, authenticator app references

Return JSON:
{
  "captcha_detected": true/false,
  "captcha_type": "recaptcha_v2|recaptcha_v3|hcaptcha|cloudflare_turnstile|custom|none",
  "two_factor_detected": true/false,
  "two_factor_type": "otp_input|authenticator|sms|email|none",
  "selector": "CSS selector of the CAPTCHA element or null",
  "confidence": 0.0 to 1.0
}

HTML:
{html_content}
"""
