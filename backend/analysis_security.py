# backend/analysis_security.py
# Security/Phishing Detection module. Owned by Member C.
# 100% RULE-BASED — regex + keyword lists only. NO API calls, NO ML model, ever.
#
# run_security_analysis(text) -> dict matching the "security" object in the API contract:
# {
#   "threat_detected": bool, "threat_type": str,
#   "urls_found": [str], "suspicious_urls": [str],
#   "emails_found": [str], "suspicious_emails": [str],
#   "social_engineering_flags": [str], "risk_level": str
# }

import re

# ---------- Configurable expected domains (brand this belongs to) ----------
# In a real deployment this would be the company's own domains.
EXPECTED_DOMAINS = {
    "ourcompany.com",
    "support.ourcompany.com",
    "billing.ourcompany.com",
}

# Common brands attackers impersonate — used for lookalike-domain detection
WATCHED_BRANDS = [
    "paypal", "amazon", "apple", "microsoft", "google", "netflix",
    "bankofamerica", "chase", "wellsfargo", "dhl", "fedex", "ups",
    "ourcompany",
]

URL_SHORTENERS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd",
    "buff.ly", "shorturl.at", "rebrand.ly", "cutt.ly",
}

# ---------- Regex patterns ----------

URL_REGEX = re.compile(
    r"""(?xi)
    \b
    (?:https?://|www\.)
    [^\s<>"')]+
    """
)

# Catches bare shortener links with no scheme/www prefix, e.g. "bit.ly/3xJk9Q"
BARE_SHORTENER_REGEX = re.compile(
    r"""(?xi)
    \b
    (?:bit\.ly|tinyurl\.com|t\.co|goo\.gl|ow\.ly|is\.gd|buff\.ly|shorturl\.at|rebrand\.ly|cutt\.ly)
    /[^\s<>"')]+
    """
)

EMAIL_REGEX = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
)

IP_URL_REGEX = re.compile(
    r"https?://(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
)

# ---------- Social engineering keyword lists ----------

URGENCY_PHRASES = [
    "urgent", "immediately", "right away", "act now", "within 24 hours",
    "your account will be suspended", "your account has been locked",
    "expires today", "final notice", "verify now", "limited time",
    "immediate action required", "your account will be closed",
]

CREDENTIAL_REQUEST_PHRASES = [
    "verify your password", "confirm your password", "enter your password",
    "verify your account", "confirm your card", "card number",
    "cvv", "social security number", "ssn", "one-time password", "otp",
    "verify your identity", "click here to verify", "update your payment information",
    "confirm your billing details", "login credentials", "confirm your identity",
]


def extract_urls(text: str) -> list:
    matches = URL_REGEX.findall(text) + BARE_SHORTENER_REGEX.findall(text)
    # normalize: add scheme to bare links for consistent downstream checks
    normalized = []
    for m in matches:
        m = m.rstrip(".,;:!?)")
        if m.startswith("www."):
            m = "http://" + m
        elif not m.lower().startswith(("http://", "https://")):
            m = "http://" + m
        normalized.append(m)
    return list(dict.fromkeys(normalized))  # dedupe, preserve order


def extract_emails(text: str) -> list:
    matches = EMAIL_REGEX.findall(text)
    return list(dict.fromkeys(matches))


def _get_domain(url: str) -> str:
    domain = re.sub(r"^https?://", "", url, flags=re.IGNORECASE)
    domain = domain.split("/")[0].split("?")[0].split(":")[0]
    return domain.lower()


def _has_lookalike_brand(domain: str) -> bool:
    """Detects brand name present in domain but domain is not the brand's real domain
    (digit-for-letter substitution, hyphenated brand names, extra subdomains, etc.)"""
    domain_clean = domain.replace("-", "").replace("0", "o").replace("1", "l").replace("3", "e")
    for brand in WATCHED_BRANDS:
        if brand in domain_clean and not domain.endswith(f"{brand}.com"):
            return True
    return False


def _is_suspicious_url(url: str) -> tuple:
    """Returns (is_suspicious: bool, reasons: list[str])"""
    reasons = []
    domain = _get_domain(url)

    if not url.lower().startswith("https://"):
        reasons.append("no HTTPS")

    if IP_URL_REGEX.match(url):
        reasons.append("IP-address URL")

    if any(domain == s or domain.endswith("." + s) for s in URL_SHORTENERS):
        reasons.append("URL shortener")

    if domain.count("-") >= 2:
        reasons.append("excessive hyphens in domain")

    if domain.count(".") >= 3:
        reasons.append("excessive subdomains")

    if _has_lookalike_brand(domain):
        reasons.append("lookalike brand domain")

    return (len(reasons) > 0, reasons)


def _is_suspicious_email(email: str) -> tuple:
    """Returns (is_suspicious: bool, reasons: list[str])"""
    reasons = []
    domain = email.split("@")[-1].lower()

    if domain not in EXPECTED_DOMAINS:
        # only flag as suspicious if it also looks like a brand-impersonation attempt
        domain_clean = domain.replace("-", "").replace("0", "o").replace("1", "l").replace("3", "e")
        for brand in WATCHED_BRANDS:
            if brand in domain_clean and not domain.endswith(f"{brand}.com"):
                reasons.append("brand lookalike domain")
                break

    return (len(reasons) > 0, reasons)


def _detect_social_engineering(text: str) -> list:
    text_lower = text.lower()
    found_urgency = [p for p in URGENCY_PHRASES if p in text_lower]
    found_credential = [p for p in CREDENTIAL_REQUEST_PHRASES if p in text_lower]

    flags = []
    if found_urgency and found_credential:
        flags.append("urgency + credential request combination")
    if found_urgency:
        flags.extend([f"urgency phrase: '{p}'" for p in found_urgency])
    if found_credential:
        flags.extend([f"credential request phrase: '{p}'" for p in found_credential])

    return flags


def _compute_risk_level(suspicious_url_count: int, suspicious_email_count: int,
                         se_flags: list, has_urgency_and_credential: bool) -> str:
    """Simple additive scoring -> Low/Medium/High/Critical"""
    score = 0
    score += suspicious_url_count * 2
    score += suspicious_email_count * 2
    score += len(se_flags)
    if has_urgency_and_credential:
        score += 3  # combination is the strongest signal

    if score == 0:
        return "Low"
    elif score <= 2:
        return "Medium"
    elif score <= 5:
        return "High"
    else:
        return "Critical"


def run_security_analysis(text: str) -> dict:
    urls_found = extract_urls(text)
    emails_found = extract_emails(text)

    suspicious_urls = []
    for url in urls_found:
        is_sus, _reasons = _is_suspicious_url(url)
        if is_sus:
            suspicious_urls.append(url)

    suspicious_emails = []
    for email in emails_found:
        is_sus, _reasons = _is_suspicious_email(email)
        if is_sus:
            suspicious_emails.append(email)

    social_engineering_flags = _detect_social_engineering(text)
    has_urgency_and_credential = any(
        "urgency + credential request combination" in f for f in social_engineering_flags
    )

    threat_detected = bool(
        suspicious_urls or suspicious_emails or has_urgency_and_credential
    )

    if not threat_detected:
        threat_type = "None"
    elif suspicious_urls or suspicious_emails:
        threat_type = "Phishing"
    else:
        threat_type = "Social Engineering"

    risk_level = _compute_risk_level(
        len(suspicious_urls), len(suspicious_emails),
        social_engineering_flags, has_urgency_and_credential
    )

    return {
        "threat_detected": threat_detected,
        "threat_type": threat_type,
        "urls_found": urls_found,
        "suspicious_urls": suspicious_urls,
        "emails_found": emails_found,
        "suspicious_emails": suspicious_emails,
        "social_engineering_flags": social_engineering_flags,
        "risk_level": risk_level,
    }


if __name__ == "__main__":
    import json

    test_messages = [
        # Phishing example
        "URGENT: Your account will be suspended in 24 hours. Verify your password immediately "
        "at http://paypa1-secure.com/verify or contact billing@paypa1-support.net",
        # IP-based + shortener
        "Please confirm your card number at http://192.168.1.5/login or use this link bit.ly/3xJk9Q",
        # Normal message 1
        "Hi, I wanted to ask when my refund for order #4521 will be processed. Thanks!",
        # Normal message 2
        "My login keeps failing even after I reset my password through the official site.",
        # Normal message with legitimate URL
        "You can check my previous ticket at https://ourcompany.com/tickets/1234",
    ]

    for i, msg in enumerate(test_messages, start=1):
        result = run_security_analysis(msg)
        print(f"--- Message {i} ---")
        print("Text:", msg)
        print("Result:", json.dumps(result, indent=2))
        print()