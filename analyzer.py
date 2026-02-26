"""
Rule-based Terms & Conditions Analyzer
No AI / ML — pure Python: regex, keyword matching, heuristics.
Supports 20 document categories.
Includes readability scoring and clause evidence highlighting.
"""

import re
import math
from dataclasses import dataclass, field
from typing import List, Optional


# ─────────────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ReadabilityScore:
    flesch_ease:       float   # 0–100  (higher = easier)
    flesch_grade:      float   # US grade level
    gunning_fog:       float   # grade level via complex words
    avg_sentence_len:  float   # words per sentence
    avg_word_len:      float   # chars per word
    complex_word_pct:  float   # % words with 3+ syllables
    grade_label:       str     # "Very Easy" … "Very Confusing"
    ease_label:        str     # plain English description


@dataclass
class KeyPoint:
    category:  str
    icon:      str
    title:     str
    detail:    str
    watch_out: bool = False
    evidence:  List[str] = field(default_factory=list)   # matched sentences


@dataclass
class RedFlag:
    message:  str
    evidence: List[str] = field(default_factory=list)


@dataclass
class AnalysisResult:
    document_type:    str
    document_summary: str
    risk_level:       str
    risk_reason:      str
    risk_score:       int
    readability:      Optional[ReadabilityScore] = None
    key_points:       List[KeyPoint]  = field(default_factory=list)
    red_flags:        List[RedFlag]   = field(default_factory=list)
    before_signing:   List[str]       = field(default_factory=list)
    word_count:       int = 0
    char_count:       int = 0

    def to_dict(self) -> dict:
        """Serialize to a plain dict (for JSON / session storage)."""
        d = {
            "document_type":    self.document_type,
            "document_summary": self.document_summary,
            "risk_level":       self.risk_level,
            "risk_reason":      self.risk_reason,
            "risk_score":       self.risk_score,
            "before_signing":   self.before_signing,
            "word_count":       self.word_count,
            "char_count":       self.char_count,
            "key_points": [
                {"category": kp.category, "icon": kp.icon, "title": kp.title,
                 "detail": kp.detail, "watch_out": kp.watch_out, "evidence": kp.evidence}
                for kp in self.key_points
            ],
            "red_flags": [
                {"message": rf.message, "evidence": rf.evidence}
                for rf in self.red_flags
            ],
        }
        if self.readability:
            d["readability"] = {
                "flesch_ease":      self.readability.flesch_ease,
                "flesch_grade":     self.readability.flesch_grade,
                "gunning_fog":      self.readability.gunning_fog,
                "avg_sentence_len": self.readability.avg_sentence_len,
                "avg_word_len":     self.readability.avg_word_len,
                "complex_word_pct": self.readability.complex_word_pct,
                "grade_label":      self.readability.grade_label,
                "ease_label":       self.readability.ease_label,
            }
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "AnalysisResult":
        r = cls(
            document_type=d["document_type"],
            document_summary=d["document_summary"],
            risk_level=d["risk_level"],
            risk_reason=d["risk_reason"],
            risk_score=d["risk_score"],
            before_signing=d["before_signing"],
            word_count=d["word_count"],
            char_count=d["char_count"],
            key_points=[
                KeyPoint(**kp) for kp in d["key_points"]
            ],
            red_flags=[
                RedFlag(**rf) for rf in d["red_flags"]
            ],
        )
        if "readability" in d:
            r.readability = ReadabilityScore(**d["readability"])
        return r


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _clean(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip()

def _has(text: str, *patterns: str) -> bool:
    t = text.lower()
    return any(re.search(p, t) for p in patterns)

def _find_evidence(text: str, *patterns: str, max_results: int = 2) -> List[str]:
    """Return up to max_results sentences that contain any of the patterns."""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    found, seen = [], set()
    for s in sentences:
        s = _clean(s)
        if len(s) < 20 or len(s) > 500:
            continue
        if any(re.search(p, s, re.IGNORECASE) for p in patterns):
            # Deduplicate by normalized form
            key = re.sub(r'\s+', ' ', s.lower()[:80])
            if key not in seen:
                seen.add(key)
                found.append(s)
        if len(found) >= max_results:
            break
    return found


# ─────────────────────────────────────────────────────────────────────────────
# Readability scoring  (pure Python — no external libraries)
# ─────────────────────────────────────────────────────────────────────────────

def _count_syllables(word: str) -> int:
    """Heuristic syllable counter — accurate enough for relative scoring."""
    word = re.sub(r'[^a-z]', '', word.lower())
    if not word:
        return 1
    # Count vowel groups (y counts as vowel in middle/end)
    count = len(re.findall(r'[aeiouy]+', word))
    # Silent 'e' at end
    if word.endswith('e') and len(word) > 2 and word[-2] not in 'aeiou':
        count -= 1
    # Compound vowels that might be split
    count += len(re.findall(r'[^aeiouy]ion', word))
    return max(1, count)

def compute_readability(text: str) -> ReadabilityScore:
    # Split into sentences and words
    sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]
    words_raw = re.findall(r"[a-zA-Z']+", text)

    num_sentences = max(len(sentences), 1)
    num_words     = max(len(words_raw), 1)

    syllables = [_count_syllables(w) for w in words_raw]
    num_syllables = sum(syllables)

    complex_words = [w for w, s in zip(words_raw, syllables) if s >= 3]
    num_complex   = len(complex_words)

    avg_sentence_len = round(num_words / num_sentences, 1)
    avg_word_len     = round(sum(len(w) for w in words_raw) / num_words, 1)
    complex_pct      = round(num_complex / num_words * 100, 1)

    # Flesch Reading Ease (0–100, higher = easier)
    flesch_ease = round(
        206.835
        - 1.015  * (num_words / num_sentences)
        - 84.6   * (num_syllables / num_words),
        1
    )
    flesch_ease = max(0.0, min(100.0, flesch_ease))

    # Flesch-Kincaid Grade Level
    flesch_grade = round(
        0.39  * (num_words / num_sentences)
        + 11.8 * (num_syllables / num_words)
        - 15.59,
        1
    )
    flesch_grade = max(0.0, flesch_grade)

    # Gunning Fog Index
    gunning_fog = round(
        0.4 * (avg_sentence_len + complex_pct),
        1
    )

    # Grade label from Flesch ease score
    if flesch_ease >= 80:
        grade_label, ease_label = "Very Easy",      "Plain English — anyone can understand this."
    elif flesch_ease >= 65:
        grade_label, ease_label = "Easy",           "Fairly accessible language — most adults can follow it."
    elif flesch_ease >= 50:
        grade_label, ease_label = "Moderate",       "Requires some concentration — equivalent to a magazine article."
    elif flesch_ease >= 35:
        grade_label, ease_label = "Difficult",      "Academic-level language — requires careful reading."
    elif flesch_ease >= 20:
        grade_label, ease_label = "Very Difficult", "Dense legal or technical writing — hard to follow for most people."
    else:
        grade_label, ease_label = "Very Confusing", "Extremely complex — consider asking a professional to explain it."

    return ReadabilityScore(
        flesch_ease=flesch_ease,
        flesch_grade=flesch_grade,
        gunning_fog=gunning_fog,
        avg_sentence_len=avg_sentence_len,
        avg_word_len=avg_word_len,
        complex_word_pct=complex_pct,
        grade_label=grade_label,
        ease_label=ease_label,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Document-type detection  (20 categories)
# ─────────────────────────────────────────────────────────────────────────────

DOC_TYPE_RULES = [
    ("Insurance Policy",
        [r'insur\w+', r'premium', r'claim', r'policyholder', r'deductible',
         r'coverage', r'beneficiar', r'underwr', r'actuar']),
    ("Loan / Credit Agreement",
        [r'\bloan\b', r'borrow', r'\blender\b', r'\bprincipal\b', r'interest rate',
         r'repayment', r'\bdefault\b', r'collateral', r'credit\s+facilit']),
    ("Mortgage Agreement",
        [r'mortgage', r'\bproperty\b', r'\bdeed\b', r'foreclosure', r'escrow',
         r'\blien\b', r'amortiz', r'real estate']),
    ("Investment / Securities",
        [r'securities', r'invest\w+', r'portfolio', r'dividend', r'\bshare\b',
         r'\bfund\b', r'\bbroker\b', r'fiduciary', r'risk\s+disclosur']),
    ("Lease / Rental Agreement",
        [r'\blease\b', r'tenancy', r'landlord', r'\btenant\b', r'\brent\b',
         r'premises', r'eviction', r'security deposit', r'notice to vacate']),
    ("Employment Contract",
        [r'employ\w+', r'\bsalary\b', r'termination', r'non.compete',
         r'confidentialit', r'severance', r'probation\w+']),
    ("SaaS / Software License",
        [r'software.as.a.service', r'\bsaas\b', r'license\s+grant',
         r'api\s+access', r'\bseat\b', r'end.user\s+licen']),
    ("Mobile App Terms",
        [r'mobile app', r'app store', r'google play', r'push notification',
         r'in.app purchase', r'device\s+permiss']),
    ("Cloud Services Agreement",
        [r'\bcloud\b', r'infrastructure', r'\buptime\b', r'\bsla\b',
         r'service level', r'data center', r'storage\s+capacit']),
    ("Open Source License",
        [r'open.source', r'\bgnu\b', r'mit license', r'apache license',
         r'redistribute', r'copyleft', r'permissive']),
    ("E-Commerce / Shopping",
        [r'shopping cart', r'refund policy', r'return policy',
         r'\bseller\b', r'\bbuyer\b', r'checkout', r'order confirmation']),
    ("Subscription Service",
        [r'subscription', r'monthly plan', r'annual plan', r'free trial',
         r'\bupgrade\b', r'\bdowngrade\b', r'billing cycle']),
    ("Streaming / Media",
        [r'stream\w+', r'content library', r'\bwatch\b', r'episode',
         r'playlist', r'download.*offline', r'simultaneous stream']),
    ("Travel & Hospitality",
        [r'booking', r'reservation', r'check.in', r'check.out',
         r'cancellation policy', r'\bhotel\b', r'\bflight\b',
         r'itinerary', r'passenger', r'travell?\w+']),
    ("Telecommunications",
        [r'telecom', r'mobile plan', r'data plan', r'roaming',
         r'network\s+coverage', r'sim card', r'\bcarrier\b', r'broadband']),
    ("Healthcare / Medical",
        [r'patient', r'healthcare', r'medical record', r'\bhipaa\b',
         r'treatment', r'physician', r'diagnos', r'health data', r'telehealth']),
    ("Financial Advisory",
        [r'financial advice', r'\badvisor\b', r'wealth management',
         r'asset management', r'fee.based', r'\bcommission\b', r'suitability']),
    ("Privacy Policy",
        [r'personal data', r'\bgdpr\b', r'data controller', r'\bcookie\b',
         r'data subject', r'\bccpa\b', r'right to erasure', r'data retention']),
    ("Social Media Platform",
        [r'\bpost\b', r'\bprofile\b', r'followers', r'content moderation',
         r'community guideline', r'\bhashtag\b', r'\bfeed\b']),
    ("Website Terms of Use",
        [r'\bwebsite\b', r'\bsite\b', r'user account', r'terms of (use|service)',
         r'acceptable use', r'hyperlink', r'web content']),
]

def detect_document_type(text: str) -> str:
    t = text.lower()
    scores = {dt: sum(len(re.findall(p, t)) for p in pats)
              for dt, pats in DOC_TYPE_RULES}
    scores = {k: v for k, v in scores.items() if v > 0}
    return max(scores, key=scores.get) if scores else "General Terms & Conditions"


# ─────────────────────────────────────────────────────────────────────────────
# Risk scoring
# ─────────────────────────────────────────────────────────────────────────────

RISK_PATTERNS = [
    (15, r'irrevocable'),
    (15, r'waive.*right'),
    (15, r'no refund'),
    (15, r'class action waiver'),
    (15, r'binding arbitration'),
    (14, r'sell.*personal (data|information)'),
    (12, r'at our sole discretion'),
    (12, r'without (prior )?notice'),
    (12, r'we may terminate.*at any time'),
    (12, r'unlimited liability'),
    (12, r'may share.*personal.*third'),
    (10, r'auto.?renew'),
    (10, r'may change.*terms.*without notice'),
    (10, r'unilateral(ly)?.*modif'),
    (15, r'foreclosure'),
    (12, r'cross.default'),
    (12, r'acceleration.*clause'),
    (12, r'wage.*garnish'),
    (10, r'non.compete'),
    (10, r'perpetual.*license'),
    (10, r'track.*location'),
    (10, r'monitor.*communication'),
    (7,  r'limitation of liability'),
    (6,  r'disclaimer of warranties'),
    (6,  r'as.is'),
    (6,  r'indemnif'),
    (5,  r'governing law'),
    (5,  r'dispute resolution'),
    (5,  r'force majeure'),
    (4,  r'intellectual property'),
    (3,  r'cookies'),
    (3,  r'aggregate.*data'),
]

def compute_risk(text: str) -> tuple:
    t = text.lower()
    score = min(sum(w for w, p in RISK_PATTERNS if re.search(p, t)), 100)
    if score >= 50:
        return "High", "Contains several aggressive clauses — liability waivers, arbitration requirements, or data-sharing terms.", score
    elif score >= 25:
        return "Medium", "Has some notable clauses around liability, data use, or cancellation that deserve attention.", score
    return "Low", "Mostly standard terms with no particularly aggressive conditions detected.", score


# ─────────────────────────────────────────────────────────────────────────────
# Key point detectors  (each now also collects evidence sentences)
# ─────────────────────────────────────────────────────────────────────────────

def _detect_payment(text):
    if not _has(text, r'payment', r'billing', r'charge', r'fee', r'price'):
        return None
    watch, parts = False, []
    if _has(text, r'automat\w+ (charge|bill|renew)'):
        parts.append("Payments may be charged automatically."); watch = True
    if _has(text, r'price.*change', r'adjust.*price', r'modify.*fee'):
        parts.append("Prices can change — check for notice requirements."); watch = True
    if _has(text, r'late.*fee', r'penalty.*payment'):
        parts.append("Late payment fees or penalties may apply."); watch = True
    detail = parts[0] if parts else "Document includes payment or billing terms."
    evidence = _find_evidence(text, r'payment', r'billing', r'charge', r'fee')
    return KeyPoint("Payment & Billing", "💳", "Payment Terms", detail, watch, evidence)

def _detect_renewal(text):
    if not _has(text, r'auto.?renew', r'automatically renew', r'renew.*subscription'):
        return None
    evidence = _find_evidence(text, r'auto.?renew', r'automatically renew')
    return KeyPoint("Auto-Renewal", "🔄", "Automatic Renewal",
        "Your subscription may renew automatically. Check how far in advance you must cancel.", True, evidence)

def _detect_cancellation(text):
    if not _has(text, r'cancel', r'terminat', r'end.*subscription'):
        return None
    watch = False
    if _has(text, r'no refund', r'non.refundable'):
        detail, watch = "Cancellations may not entitle you to a refund.", True
    elif _has(text, r'cancel.*any time', r'anytime'):
        detail = "You can cancel at any time, but verify whether unused periods are refunded."
    elif _has(text, r'notice.*cancel', r'cancel.*notice'):
        detail, watch = "A notice period may be required before cancellation takes effect.", True
    else:
        detail = "Cancellation terms are defined in this document."
    evidence = _find_evidence(text, r'cancel\w*', r'terminat\w*')
    return KeyPoint("Cancellation", "❌", "Cancellation Policy", detail, watch, evidence)

def _detect_refund(text):
    if not _has(text, r'refund', r'money.back', r'chargeback'):
        return None
    evidence = _find_evidence(text, r'refund', r'money.back')
    if _has(text, r'no refund', r'non.refundable', r'all sales final'):
        return KeyPoint("Refunds", "💰", "Refund Policy",
            "No refunds are available — all purchases are final.", True, evidence)
    m = re.search(r'(\d+).day', text, re.IGNORECASE)
    detail = f"A {m.group(1)}-day refund window is offered — verify the conditions." if m else "Refund terms are addressed."
    return KeyPoint("Refunds", "💰", "Refund Policy", detail, False, evidence)

def _detect_data_privacy(text):
    if not _has(text, r'personal (data|information)', r'privacy', r'collect.*data'):
        return None
    evidence = _find_evidence(text, r'personal (data|information)', r'collect.*data', r'share.*data')
    if _has(text, r'sell.*data', r'third.party.*sell'):
        return KeyPoint("Privacy & Data", "🔒", "Data & Privacy",
            "Your personal data may be sold to third parties.", True, evidence)
    if _has(text, r'share.*third.part', r'third.part.*share'):
        return KeyPoint("Privacy & Data", "🔒", "Data & Privacy",
            "Your data may be shared with third parties — check which ones and why.", True, evidence)
    detail = "GDPR/CCPA-compliant data handling is referenced." if _has(text, r'gdpr', r'ccpa') else "The document describes how your personal data is handled."
    return KeyPoint("Privacy & Data", "🔒", "Data & Privacy", detail, False, evidence)

def _detect_cookies(text):
    if not _has(text, r'cookie', r'tracking', r'web beacon', r'pixel'):
        return None
    evidence = _find_evidence(text, r'cookie', r'tracking', r'web beacon')
    watch = _has(text, r'third.party.*cookie', r'advertis.*cookie')
    detail = "Third-party and advertising cookies may be placed on your device." if watch else "Cookies and tracking technologies are used."
    return KeyPoint("Cookies & Tracking", "🍪", "Cookies & Tracking", detail, watch, evidence)

def _detect_liability(text):
    if not _has(text, r'liability', r'liable', r'indemnif'):
        return None
    evidence = _find_evidence(text, r'liabilit', r'indemnif')
    watch = False
    if _has(text, r'unlimited liability'):
        detail, watch = "You may be exposed to unlimited financial liability.", True
    elif _has(text, r'limitation of liability', r'not liable'):
        detail, watch = "The provider limits its own liability — you may have limited recourse for damages.", True
    else:
        detail = "The document includes liability clauses."
    if _has(text, r'indemnif'):
        detail += " You may be required to indemnify the provider against third-party claims."
        watch = True
    return KeyPoint("Liability", "⚠️", "Liability & Indemnification", detail, watch, evidence)

def _detect_arbitration(text):
    if not _has(text, r'arbitrat', r'class action', r'dispute resolution', r'jurisdiction'):
        return None
    evidence = _find_evidence(text, r'arbitrat', r'class action', r'dispute')
    watch = False
    detail = "Dispute resolution procedures are outlined."
    if _has(text, r'binding arbitration'):
        detail, watch = "You must use binding arbitration to resolve disputes — you may not sue in court.", True
    if _has(text, r'class action waiver'):
        detail += " Class action lawsuits are waived."; watch = True
    return KeyPoint("Dispute Resolution", "⚖️", "Disputes & Arbitration", detail, watch, evidence)

def _detect_ip(text):
    if not _has(text, r'intellectual property', r'copyright', r'trademark', r'content.*license', r'user.generated'):
        return None
    evidence = _find_evidence(text, r'intellectual property', r'copyright', r'license.*content')
    watch = _has(text, r'grant.*license.*content', r'royalty.free', r'perpetual.*license')
    detail = "You grant the platform a broad license to use your content." if watch else "Intellectual property ownership is addressed."
    return KeyPoint("Intellectual Property", "©️", "Content & IP Rights", detail, watch, evidence)

def _detect_termination(text):
    if not _has(text, r'terminat.*account', r'suspend.*account', r'sole.*discretion'):
        return None
    evidence = _find_evidence(text, r'terminat.*account', r'suspend.*account', r'sole.*discretion')
    watch = False
    detail = "The provider can terminate or suspend accounts under defined conditions."
    if _has(text, r'without (prior )?notice') and _has(text, r'terminat'):
        detail, watch = "Your account may be terminated without prior notice at their discretion.", True
    return KeyPoint("Account Termination", "🚫", "Account Suspension / Termination", detail, watch, evidence)

def _detect_changes(text):
    if not _has(text, r'modif.*terms', r'change.*terms', r'amend.*agreement', r'update.*terms'):
        return None
    evidence = _find_evidence(text, r'modif.*terms', r'change.*terms', r'amend.*agreement')
    watch = _has(text, r'without.*notice', r'at any time.*modif')
    detail = "Terms can be changed at any time without notice — continued use implies acceptance." if watch else "The provider can update these terms over time."
    return KeyPoint("Terms Changes", "📝", "Right to Modify Terms", detail, watch, evidence)

def _detect_governing_law(text):
    if not _has(text, r'governing law', r'jurisdiction', r'laws of the state'):
        return None
    m = re.search(r'laws? of (the )?([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)', text)
    j = m.group(2) if m else "a specific jurisdiction"
    evidence = _find_evidence(text, r'governing law', r'jurisdiction')
    return KeyPoint("Governing Law", "🏛️", "Applicable Law & Jurisdiction",
        f"This agreement is governed by the laws of {j}. Disputes may need to be resolved there.", False, evidence)

def _detect_non_compete(text):
    if not _has(text, r'non.compete', r'non.solicit', r'restraint of trade'):
        return None
    detail = "A non-compete or non-solicitation clause is present — you may be restricted from working for competitors."
    m = re.search(r'(\d+)\s*(month|year)', text, re.IGNORECASE)
    if m: detail += f" The restriction period appears to be {m.group(1)} {m.group(2)}(s)."
    evidence = _find_evidence(text, r'non.compete', r'non.solicit', r'restraint of trade')
    return KeyPoint("Non-Compete", "🚷", "Non-Compete Clause", detail, True, evidence)

def _detect_loan_default(text):
    if not _has(text, r'default', r'acceleration', r'foreclosure', r'repossess'):
        return None
    evidence = _find_evidence(text, r'default', r'foreclosure', r'repossess', r'acceleration')
    return KeyPoint("Default & Consequences", "💥", "Default Provisions",
        "The document outlines consequences for default — this may include acceleration of full repayment, asset seizure, or foreclosure.", True, evidence)

def _detect_health_data(text):
    if not _has(text, r'hipaa', r'health.*data', r'medical.*record', r'protected health', r'\bphi\b'):
        return None
    evidence = _find_evidence(text, r'hipaa', r'health.*data', r'medical.*record')
    watch = _has(text, r'share.*health', r'disclose.*health', r'third.*health')
    detail = "Your health data may be shared with third parties — verify scope and purpose." if watch else "Health data is involved. HIPAA or equivalent protections may apply."
    return KeyPoint("Health Data", "🏥", "Health & Medical Data", detail, watch, evidence)

def _detect_telecom(text):
    if not _has(text, r'roaming', r'data cap', r'fair use', r'throttl', r'network management'):
        return None
    evidence = _find_evidence(text, r'roaming', r'throttl', r'data cap')
    watch = False
    detail = "Network usage policies are defined."
    if _has(text, r'throttl', r'speed.*reduc'):
        detail, watch = "Your data speeds may be throttled after exceeding a usage threshold.", True
    if _has(text, r'roaming'):
        detail += " Roaming charges may apply outside your home network."; watch = True
    return KeyPoint("Network & Roaming", "📡", "Data Limits & Roaming", detail, watch, evidence)

def _detect_security_deposit(text):
    if not _has(text, r'security deposit', r'bond\b', r'damage.*deposit'):
        return None
    evidence = _find_evidence(text, r'security deposit', r'bond', r'deposit')
    return KeyPoint("Security Deposit", "🏦", "Security Deposit",
        "A security deposit is required. Review the conditions under which it can be withheld or deducted.", True, evidence)

def _detect_force_majeure(text):
    if not _has(text, r'force majeure', r'act of god', r'beyond.*control', r'unforeseeable'):
        return None
    evidence = _find_evidence(text, r'force majeure', r'act of god', r'beyond.*control')
    return KeyPoint("Force Majeure", "🌪️", "Force Majeure",
        "A force majeure clause limits the provider's obligations during extraordinary events (natural disasters, pandemics, etc.).", False, evidence)

def _detect_sla(text):
    if not _has(text, r'\bsla\b', r'service level', r'uptime', r'availability.*%', r'downtime'):
        return None
    evidence = _find_evidence(text, r'uptime', r'service level', r'downtime')
    m = re.search(r'(\d{2,3}(?:\.\d+)?)\s*%', text)
    uptime = f"{m.group(1)}%" if m else "a defined"
    watch = _has(text, r'no credit', r'sole remedy.*credit', r'not liable.*downtime')
    detail = f"An SLA guarantees {uptime} uptime."
    if watch: detail += " However, compensation for downtime may be limited to service credits only."
    return KeyPoint("Service Level", "📊", "Uptime & SLA Guarantee", detail, watch, evidence)

def _detect_age_restriction(text):
    if not _has(text, r'(\d+)\s*years? of age', r'must be\s*\d+', r'age.*requirement', r'minors?'):
        return None
    m = re.search(r'(\d+)\s*years? of age|must be (\d+)', text, re.IGNORECASE)
    age = m.group(1) or m.group(2) if m else "a minimum"
    evidence = _find_evidence(text, r'years? of age', r'must be \d+', r'minor')
    return KeyPoint("Age Restriction", "🔞", "Age Requirement",
        f"Users must be at least {age} years old. Parental consent may be required for minors.", False, evidence)


DETECTORS = [
    _detect_payment, _detect_renewal, _detect_cancellation, _detect_refund,
    _detect_data_privacy, _detect_cookies, _detect_liability, _detect_arbitration,
    _detect_ip, _detect_termination, _detect_changes, _detect_governing_law,
    _detect_non_compete, _detect_loan_default, _detect_health_data,
    _detect_telecom, _detect_security_deposit, _detect_force_majeure,
    _detect_sla, _detect_age_restriction,
]


# ─────────────────────────────────────────────────────────────────────────────
# Red flag detector  (now returns RedFlag objects with evidence)
# ─────────────────────────────────────────────────────────────────────────────

RED_FLAG_RULES = [
    (r'sell.*personal (data|information)',          "May sell your personal data to third parties.",              [r'sell.*personal', r'personal.*sold']),
    (r'share.*with.*third.part',                    "Your data may be shared with unspecified third parties.",   [r'share.*third', r'third.part.*receiv']),
    (r'track.*location',                            "Your location data may be tracked.",                        [r'track.*location', r'location.*track']),
    (r'monitor.*communication',                     "Provider may monitor your private communications.",         [r'monitor.*communicat']),
    (r'class action waiver',                        "Waives your right to participate in class action lawsuits.",[r'class action']),
    (r'binding arbitration',                        "Requires binding arbitration — limits your ability to sue.",[r'binding arbitration', r'arbitrat']),
    (r'waive.*right',                               "Contains clauses where you waive important legal rights.",  [r'waive.*right', r'right.*waiv']),
    (r'irrevocable.*licen',                         "Grants an irrevocable license over your content.",          [r'irrevocable.*licen']),
    (r'perpetual.*licen.*royalty.free',             "Grants unlimited, perpetual, royalty-free use of your content.", [r'perpetual.*licen', r'royalty.free']),
    (r'no refund|non.refundable|all sales final',   "No refunds under any circumstances.",                       [r'no refund', r'non.refundable']),
    (r'accelerat.*repayment|full.*amount.*due',     "Default may trigger immediate repayment of full balance.",  [r'accelerat', r'full.*amount.*due']),
    (r'wage.*garnish',                              "Wages may be garnished in case of default.",                [r'wage.*garnish']),
    (r'(modif|change|amend).*without.*notice',      "Terms can be changed without notifying you.",               [r'without.*notice', r'change.*terms']),
    (r'terminat.*without (prior )?notice',          "Account can be terminated without any notice.",             [r'terminat.*without.*notice']),
    (r'at our sole discretion',                     "Provider has unchecked discretion on key decisions.",       [r'sole discretion']),
    (r'unilateral.*modif',                          "Provider can unilaterally modify the agreement.",           [r'unilateral']),
    (r'not responsible.*any (loss|damage)',         "Provider disclaims all responsibility for losses.",         [r'not responsible.*loss', r'not liable.*damage']),
    (r'indemnif.*attorney.*fees',                   "You may be liable for the provider's legal fees.",          [r'indemnif.*attorney', r'attorney.*fees']),
    (r'foreclosure',                                "Non-payment may result in foreclosure of your property.",   [r'foreclosure']),
    (r'non.compete.*(\d+)\s*year',                  "Non-compete clause restricts you for a multi-year period.", [r'non.compete.*year']),
    (r'cross.default',                              "Default on one obligation may trigger default on all.",     [r'cross.default']),
    (r'repossess',                                  "Assets may be repossessed in case of default.",             [r'repossess']),
]

def detect_red_flags(text: str) -> List[RedFlag]:
    t = text.lower()
    flags = []
    seen_messages = set()
    for trigger, message, evidence_pats in RED_FLAG_RULES:
        if re.search(trigger, t) and message not in seen_messages:
            seen_messages.add(message)
            evidence = _find_evidence(text, *evidence_pats)
            flags.append(RedFlag(message=message, evidence=evidence))
    return flags


# ─────────────────────────────────────────────────────────────────────────────
# Before-signing checklist
# ─────────────────────────────────────────────────────────────────────────────

def build_checklist(text: str, doc_type: str, risk_level: str) -> List[str]:
    items = []
    if _has(text, r'auto.?renew', r'automatically renew'):
        items.append("Confirm the auto-renewal date and how to cancel before it triggers.")
    if _has(text, r'binding arbitration'):
        items.append("Understand that by signing you likely give up your right to sue in court.")
    if _has(text, r'personal data', r'data.*collect'):
        items.append("Review exactly what personal data is collected and who it is shared with.")
    if _has(text, r'no refund', r'non.refundable'):
        items.append("Note there are no refunds — be certain before committing.")
    if _has(text, r'foreclosure', r'repossess', r'collateral'):
        items.append("Understand what assets are at risk if you default on your obligations.")
    if _has(text, r'non.compete', r'non.solicit'):
        items.append("Review the non-compete clause — it may restrict future employment.")
    if _has(text, r'hipaa', r'health.*data', r'medical.*record'):
        items.append("Verify how your health data is stored, protected, and who can access it.")
    if _has(text, r'roaming', r'data cap', r'throttl'):
        items.append("Check data caps, throttling thresholds, and roaming charges carefully.")
    if _has(text, r'governing law', r'jurisdiction'):
        m = re.search(r'laws? of (the )?([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)', text)
        if m: items.append(f"Disputes will be handled under {m.group(2)} law — check if this affects you.")
    if _has(text, r'indemnif'):
        items.append("Understand the indemnification clause — you may be financially responsible for third-party claims.")
    if _has(text, r'intellectual property', r'license.*content'):
        items.append("Check what rights you grant to the platform over content you upload.")
    if risk_level == "High":
        items.append("Given the high risk level, consider having a legal professional review this document.")
    if not items:
        items.append("Read the full document carefully before agreeing.")
        items.append("Check for any trial periods, fees, or commitments involved.")
    items.append("Keep a copy of this document for your records once signed.")
    return items[:7]


# ─────────────────────────────────────────────────────────────────────────────
# Summary templates
# ─────────────────────────────────────────────────────────────────────────────

SUMMARY_TEMPLATES = {
    "Insurance Policy":           "This is an insurance policy outlining coverage terms, exclusions, premiums, and claim procedures. It defines your rights as a policyholder and what events or losses are covered.",
    "Loan / Credit Agreement":    "This is a loan or credit agreement governing borrowed funds, repayment schedules, interest rates, and consequences of default.",
    "Mortgage Agreement":         "This is a mortgage agreement securing a loan against real property. It covers repayment terms, interest, default consequences including foreclosure rights.",
    "Investment / Securities":    "This is an investment or securities agreement covering risk disclosures, fees, fiduciary obligations, and the management of your assets or portfolio.",
    "Lease / Rental Agreement":   "This is a lease or rental agreement outlining tenancy terms, rent obligations, maintenance responsibilities, and conditions for eviction.",
    "Employment Contract":        "This is an employment agreement covering compensation, confidentiality, intellectual property, non-compete obligations, and termination conditions.",
    "SaaS / Software License":    "This is a software or SaaS subscription agreement governing usage rights, billing, and the provider's ability to modify or terminate the service.",
    "Mobile App Terms":           "These are Terms of Service for a mobile application covering acceptable use, in-app purchases, data handling, and your rights as a user.",
    "Cloud Services Agreement":   "This is a cloud services agreement covering infrastructure access, uptime guarantees (SLAs), data ownership, and service availability.",
    "Open Source License":        "This is an open-source license governing how the software can be used, modified, and redistributed.",
    "E-Commerce / Shopping":      "This is an e-commerce agreement covering purchases, returns, refunds, and seller/buyer obligations on the platform.",
    "Subscription Service":       "This is a subscription agreement governing recurring billing, plan features, upgrade/downgrade rights, and cancellation.",
    "Streaming / Media":          "This is a streaming or media service agreement covering content access, billing, simultaneous streams, and usage restrictions.",
    "Travel & Hospitality":       "This is a travel or hospitality agreement covering bookings, cancellations, refunds, passenger obligations, and liability for travel disruptions.",
    "Telecommunications":         "This is a telecommunications agreement covering your mobile or broadband plan, data limits, roaming charges, and network usage policies.",
    "Healthcare / Medical":       "This is a healthcare or medical services agreement covering patient rights, data privacy (HIPAA), treatment consent, and billing.",
    "Financial Advisory":         "This is a financial advisory agreement covering the scope of advice, fee structures, fiduciary duty, conflicts of interest, and liability.",
    "Privacy Policy":             "This is a Privacy Policy describing what personal data is collected, how it is used, who it is shared with, and your rights regarding that data.",
    "Social Media Platform":      "These are Terms of Service for a social media platform covering content rights, community standards, data use, and account management.",
    "Website Terms of Use":       "These are Website Terms of Use governing how you may access and interact with the site, including user accounts, content, and liability.",
    "General Terms & Conditions": "This is a general Terms & Conditions document outlining the rules, rights, and obligations between you and the provider.",
}

def build_summary(doc_type: str, text: str) -> str:
    base = SUMMARY_TEMPLATES.get(doc_type, SUMMARY_TEMPLATES["General Terms & Conditions"])
    if len(text.split()) > 3000:
        base += " The document is comprehensive — take time to read key sections carefully."
    return base


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def analyze(text: str) -> AnalysisResult:
    text = _clean(text)
    if not text:
        raise ValueError("Empty document.")

    doc_type = detect_document_type(text)
    risk_level, risk_reason, risk_score = compute_risk(text)

    return AnalysisResult(
        document_type=doc_type,
        document_summary=build_summary(doc_type, text),
        risk_level=risk_level,
        risk_reason=risk_reason,
        risk_score=risk_score,
        readability=compute_readability(text),
        key_points=[r for r in (d(text) for d in DETECTORS) if r is not None],
        red_flags=detect_red_flags(text),
        before_signing=build_checklist(text, doc_type, risk_level),
        word_count=len(text.split()),
        char_count=len(text),
    )
