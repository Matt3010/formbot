FORM_ANALYSIS_PROMPT = """
You are a web form analyzer. Analyze the following HTML and identify ALL forms on the page.

For each form, return a JSON object with this EXACT structure:

{
  "forms": [
    {
      "form_selector": "CSS selector for the <form> tag (prefer #id, then .class, then tag[attribute])",
      "form_type": "login|registration|search|contact|data_entry|payment|other",
      "confidence": 0.0 to 1.0,
      "submit_selector": "CSS selector for the submit button",
      "captcha_detected": true/false,
      "captcha_type": "recaptcha_v2|recaptcha_v3|hcaptcha|cloudflare_turnstile|custom|none",
      "fields": [
        {
          "field_selector": "CSS selector (prefer #id)",
          "field_name": "name or id attribute value",
          "field_type": "text|password|email|tel|number|url|date|select|checkbox|radio|textarea|file|hidden",
          "field_purpose": "username|password|email|first_name|last_name|phone|address|city|zip|country|search_query|message|subject|amount|card_number|cvv|expiry|other",
          "required": true/false,
          "options": ["option1", "option2"]
        }
      ]
    }
  ],
  "page_requires_login": true/false,
  "two_factor_detected": true/false,
  "suggested_flow": "Brief description of the recommended navigation flow"
}

Rules:
- Return ONLY valid JSON, no extra text
- Use specific, unique CSS selectors (prefer IDs over classes)
- Detect hidden fields but mark them as type "hidden"
- Identify CAPTCHA elements (iframes, divs with captcha-related classes)
- Detect 2FA elements (OTP inputs, authenticator prompts)
- If no forms found, return {"forms": [], "page_requires_login": false}
- Each field MUST have its own separate object in the "fields" array. Never group multiple fields into a single entry.
- Each "field_selector" MUST be a single, valid CSS selector that uniquely identifies one element (e.g. "#email", "input[name='phone']"). Never combine multiple selectors in one string.
- "page_requires_login" must be true ONLY if the page contains a form with a visible password field that blocks access to the main content. A contact form, newsletter signup, search form, or any form without a password field is NOT a login page.
- A form that only asks for email, name, phone, or message is a contact/data-entry form, NOT a login form.

HTML to analyze:
{html_content}
"""
