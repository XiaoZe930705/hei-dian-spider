from __future__ import annotations

import re
from collections import defaultdict
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .url_utils import is_same_site


def _parse_set_cookie_flags(set_cookie_value: str) -> dict[str, bool]:
    parts = [p.strip() for p in (set_cookie_value or "").split(";") if p.strip()]
    lower = [p.lower() for p in parts]
    return {
        "secure": any(p == "secure" for p in lower),
        "httponly": any(p == "httponly" for p in lower),
        "samesite": any(p.startswith("samesite=") for p in lower),
    }


def _get_all_set_cookie(headers) -> list[str]:
    # requests/urllib3 版本差異：有些有 getlist，有些沒有
    if hasattr(headers, "getlist"):
        try:
            return list(headers.getlist("Set-Cookie"))
        except Exception:
            pass

    value = headers.get("Set-Cookie")
    if not value:
        return []
    # 多個 cookie 有時用逗號串起來（不可靠，但作為退化方案）
    return [v.strip() for v in value.split(",") if v.strip()]


def _grade(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


def analyze_security(seed_url: str, final_url: str, html: str, resp) -> dict:
    """
    OWASP Top 10 不是單靠靜態抓取就能完整檢測。
    這裡提供「可觀測、低侵入」的啟發式檢查與評分，重點放在：
    - HTTPS / HSTS / 安全標頭
    - Cookie flags
    - 混合內容（HTTPS 頁面引用 http://）
    - 外部腳本未設 SRI（integrity）
    - CORS wildcard
    """
    headers = resp.headers
    findings: list[str] = []
    category_hits: dict[str, int] = defaultdict(int)

    final_scheme = (urlparse(final_url).scheme or "").lower()
    is_https = final_scheme == "https"
    if not is_https:
        findings.append("non_https")
        category_hits["A02"] += 1

    hsts = headers.get("Strict-Transport-Security")
    if is_https and not hsts:
        findings.append("missing_hsts")
        category_hits["A02"] += 1

    csp = headers.get("Content-Security-Policy")
    if not csp:
        findings.append("missing_csp")
        category_hits["A05"] += 1

    xfo = headers.get("X-Frame-Options")
    if not xfo and not (csp and re.search(r"frame-ancestors\\s", csp, re.I)):
        findings.append("missing_clickjacking_protection")
        category_hits["A05"] += 1

    xcto = (headers.get("X-Content-Type-Options") or "").lower()
    if xcto != "nosniff":
        findings.append("missing_x_content_type_options")
        category_hits["A05"] += 1

    if not headers.get("Referrer-Policy"):
        findings.append("missing_referrer_policy")
        category_hits["A05"] += 1

    if not headers.get("Permissions-Policy"):
        findings.append("missing_permissions_policy")
        category_hits["A05"] += 1

    aco = headers.get("Access-Control-Allow-Origin")
    if aco == "*":
        findings.append("cors_wildcard")
        category_hits["A05"] += 1

    if headers.get("Server"):
        findings.append("server_header_present")
        category_hits["A05"] += 1

    if headers.get("X-Powered-By"):
        findings.append("x_powered_by_present")
        category_hits["A05"] += 1

    set_cookies = _get_all_set_cookie(headers)
    insecure_cookie_count = 0
    for sc in set_cookies:
        flags = _parse_set_cookie_flags(sc)
        if not flags["secure"] or not flags["httponly"] or not flags["samesite"]:
            insecure_cookie_count += 1
    if insecure_cookie_count:
        findings.append(f"insecure_cookies:{insecure_cookie_count}")
        category_hits["A07"] += 1
        category_hits["A02"] += 1

    soup = BeautifulSoup(html or "", "html.parser")

    mixed_count = 0
    if is_https:
        for tag in soup.find_all(["a", "img", "script", "link"]):
            attr = "href" if tag.name in ("a", "link") else "src"
            v = (tag.get(attr) or "").strip()
            if v.lower().startswith("http://"):
                mixed_count += 1
    if mixed_count:
        findings.append(f"mixed_content:{mixed_count}")
        category_hits["A02"] += 1

    insecure_password_forms = 0
    for form in soup.find_all("form"):
        if not form.find("input", attrs={"type": re.compile(r"^password$", re.I)}):
            continue
        action = (form.get("action") or "").strip()
        if not action:
            continue
        if action.lower().startswith("http://"):
            insecure_password_forms += 1
        # 同站但不是 https 的情況，也視為風險（若 seed 是 https）
        elif action.startswith("/") and is_https:
            # relative action, assume same scheme; ok
            pass
    if insecure_password_forms:
        findings.append(f"insecure_password_form_action:{insecure_password_forms}")
        category_hits["A07"] += 1

    sri_missing_external_scripts = 0
    for script in soup.find_all("script", src=True):
        src = (script.get("src") or "").strip()
        if not src:
            continue
        parsed = urlparse(src)
        if parsed.scheme in ("http", "https") and not is_same_site(src, seed_url):
            if not script.get("integrity"):
                sri_missing_external_scripts += 1
    if sri_missing_external_scripts:
        findings.append(f"external_script_missing_sri:{sri_missing_external_scripts}")
        category_hits["A08"] += 1

    score = 100
    deductions = [
        ("non_https", 20),
        ("missing_hsts", 10),
        ("missing_csp", 10),
        ("missing_clickjacking_protection", 5),
        ("missing_x_content_type_options", 5),
        ("missing_referrer_policy", 3),
        ("missing_permissions_policy", 3),
        ("cors_wildcard", 5),
        ("server_header_present", 2),
        ("x_powered_by_present", 2),
        ("mixed_content", min(10, mixed_count * 2)),
        ("insecure_cookies", min(10, insecure_cookie_count * 5)),
        ("insecure_password_form_action", min(10, insecure_password_forms * 10)),
        ("external_script_missing_sri", min(6, sri_missing_external_scripts * 3)),
    ]

    finding_set = set(findings)
    for key, points in deductions:
        if key in finding_set:
            score -= points
        elif key == "mixed_content" and mixed_count:
            score -= points
        elif key == "insecure_cookies" and insecure_cookie_count:
            score -= points
        elif key == "insecure_password_form_action" and insecure_password_forms:
            score -= points
        elif key == "external_script_missing_sri" and sri_missing_external_scripts:
            score -= points

    score = max(0, min(100, int(score)))

    owasp_top10 = {
        "A02_Cryptographic_Failures": int(category_hits.get("A02", 0)),
        "A05_Security_Misconfiguration": int(category_hits.get("A05", 0)),
        "A07_Identification_and_Authentication_Failures": int(category_hits.get("A07", 0)),
        "A08_Software_and_Data_Integrity_Failures": int(category_hits.get("A08", 0)),
    }

    return {
        "score": score,
        "grade": _grade(score),
        "findings": findings,
        "owasp_top10_hits": owasp_top10,
        "signals": {
            "https": is_https,
            "hsts": bool(hsts),
            "csp": bool(csp),
            "x_frame_options": bool(xfo),
            "x_content_type_options": xcto == "nosniff",
            "referrer_policy": bool(headers.get("Referrer-Policy")),
            "permissions_policy": bool(headers.get("Permissions-Policy")),
            "cors_wildcard": aco == "*",
            "mixed_content_count": mixed_count,
            "insecure_cookie_count": insecure_cookie_count,
            "external_script_missing_sri_count": sri_missing_external_scripts,
        },
    }

