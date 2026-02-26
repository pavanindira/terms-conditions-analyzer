"""
multi_compare.py — Rank N documents (3–8) against each other.

Produces:
  • A ranked leaderboard (1 = safest, N = riskiest)
  • A category matrix showing every doc × every category
  • Per-doc red flag breakdown
  • A plain-English recommendation
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict
from analyzer import AnalysisResult, KeyPoint


# ─────────────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DocRanking:
    """A single document's position in the ranked leaderboard."""
    rank:        int
    name:        str
    result:      AnalysisResult
    total_score: float          # Lower = safer (composite score)
    watch_count: int            # Number of key points with watch_out=True
    strengths:   List[str] = field(default_factory=list)   # What it does well
    weaknesses:  List[str] = field(default_factory=list)   # Key concerns

@dataclass
class MatrixCell:
    """One cell in the category × document matrix."""
    present:   bool
    watch_out: bool
    detail:    str
    # visual state: "good" | "warn" | "missing"
    @property
    def state(self) -> str:
        if not self.present:  return "missing"
        if self.watch_out:    return "warn"
        return "good"

@dataclass
class CategoryRow:
    """One row in the matrix — one category across all docs."""
    category: str
    icon:     str
    cells:    List[MatrixCell]   # one per doc, in same order as rankings

@dataclass
class MultiCompareResult:
    doc_names:      List[str]
    rankings:       List[DocRanking]    # sorted 1 (best) → N (worst)
    matrix:         List[CategoryRow]
    winner_name:    str
    winner_reason:  str
    recommendation: str                 # 2–3 sentence plain-English pick
    llm_pick:       str = ""
    llm_model:      str = ""
    llm_enhanced:   bool = False

    def to_dict(self) -> dict:
        return {
            "doc_names":      self.doc_names,
            "winner_name":    self.winner_name,
            "winner_reason":  self.winner_reason,
            "recommendation": self.recommendation,
            "llm_pick":       self.llm_pick,
            "llm_model":      self.llm_model,
            "llm_enhanced":   self.llm_enhanced,
            "rankings": [
                {
                    "rank":        r.rank,
                    "name":        r.name,
                    "result":      r.result.to_dict(),
                    "total_score": r.total_score,
                    "watch_count": r.watch_count,
                    "strengths":   r.strengths,
                    "weaknesses":  r.weaknesses,
                }
                for r in self.rankings
            ],
            "matrix": [
                {
                    "category": row.category,
                    "icon":     row.icon,
                    "cells": [
                        {"present": c.present, "watch_out": c.watch_out, "detail": c.detail}
                        for c in row.cells
                    ],
                }
                for row in self.matrix
            ],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MultiCompareResult":
        from analyzer import AnalysisResult as AR
        rankings = []
        for r in d["rankings"]:
            rankings.append(DocRanking(
                rank=r["rank"], name=r["name"],
                result=AR.from_dict(r["result"]),
                total_score=r["total_score"],
                watch_count=r["watch_count"],
                strengths=r["strengths"],
                weaknesses=r["weaknesses"],
            ))
        matrix = []
        for row in d["matrix"]:
            cells = [MatrixCell(c["present"], c["watch_out"], c["detail"])
                     for c in row["cells"]]
            matrix.append(CategoryRow(row["category"], row["icon"], cells))

        return cls(
            doc_names=d["doc_names"],
            rankings=rankings,
            matrix=matrix,
            winner_name=d["winner_name"],
            winner_reason=d["winner_reason"],
            recommendation=d["recommendation"],
            llm_pick=d.get("llm_pick", ""),
            llm_model=d.get("llm_model", ""),
            llm_enhanced=d.get("llm_enhanced", False),
        )


# ─────────────────────────────────────────────────────────────────────────────
# Scoring
# ─────────────────────────────────────────────────────────────────────────────

def _composite_score(result: AnalysisResult) -> float:
    """
    Lower = safer. Composite of:
      - Risk score (0–100)          weight 0.5
      - Red flag count × 4          weight 0.3
      - Watch-out key point count×3 weight 0.2
    """
    watch_count = sum(1 for kp in result.key_points if kp.watch_out)
    return (
        result.risk_score * 0.5
        + len(result.red_flags) * 4 * 0.3
        + watch_count * 3 * 0.2
    )

def _strengths(name: str, result: AnalysisResult, all_results: list) -> List[str]:
    """Generate plain-English strengths relative to peers."""
    items = []
    avg_risk = sum(r.risk_score for _, r in all_results) / len(all_results)
    avg_flags = sum(len(r.red_flags) for _, r in all_results) / len(all_results)

    if result.risk_score < avg_risk - 10:
        items.append(f"Risk score ({result.risk_score}/100) is well below average")
    if len(result.red_flags) < avg_flags:
        items.append("Fewer red flags than most alternatives")
    good_pts = [kp for kp in result.key_points if not kp.watch_out]
    if good_pts:
        items.append(f"Favourable terms on: {', '.join(kp.category for kp in good_pts[:3])}")
    if result.readability and result.readability.flesch_ease >= 50:
        items.append("Written in relatively plain language")
    return items[:3] if items else ["No particular strengths identified"]

def _weaknesses(name: str, result: AnalysisResult, all_results: list) -> List[str]:
    """Generate plain-English weaknesses."""
    items = []
    avg_risk = sum(r.risk_score for _, r in all_results) / len(all_results)

    if result.risk_score > avg_risk + 10:
        items.append(f"Risk score ({result.risk_score}/100) is above average")
    if result.red_flags:
        items.append(f"{len(result.red_flags)} red flag(s) detected")
    watch_pts = [kp for kp in result.key_points if kp.watch_out]
    if watch_pts:
        items.append(f"Concerning clauses: {', '.join(kp.category for kp in watch_pts[:3])}")
    if result.readability and result.readability.flesch_ease < 35:
        items.append("Complex, hard-to-follow language")
    return items[:3] if items else []


# ─────────────────────────────────────────────────────────────────────────────
# Category matrix
# ─────────────────────────────────────────────────────────────────────────────

MATRIX_CATEGORY_ORDER = [
    "Privacy & Data",
    "Dispute Resolution",
    "Account Termination",
    "Auto-Renewal",
    "Cancellation",
    "Refunds",
    "Payment & Billing",
    "Liability",
    "Intellectual Property",
    "Terms Changes",
    "Cookies & Tracking",
    "Non-Compete",
    "Health Data",
    "Default & Consequences",
    "Security Deposit",
    "Network & Roaming",
    "Service Level",
    "Force Majeure",
    "Age Restriction",
    "Governing Law",
]

def _build_matrix(doc_pairs: list, ranked_names: List[str]) -> List[CategoryRow]:
    """
    Build category × doc matrix.
    doc_pairs = [(name, AnalysisResult), ...]  in original order
    ranked_names = names in rank order (best first) — used for column order
    """
    # Reorder docs by rank
    name_to_result = {name: r for name, r in doc_pairs}
    ordered = [(n, name_to_result[n]) for n in ranked_names]

    # Collect all categories across all docs
    all_cats: Dict[str, str] = {}   # category → icon
    for _, result in ordered:
        for kp in result.key_points:
            if kp.category not in all_cats:
                all_cats[kp.category] = kp.icon

    # Sort by canonical order
    def sort_key(c):
        try: return MATRIX_CATEGORY_ORDER.index(c)
        except ValueError: return 999

    rows = []
    for cat in sorted(all_cats.keys(), key=sort_key):
        icon = all_cats[cat]
        cells = []
        for _, result in ordered:
            kp = next((k for k in result.key_points if k.category == cat), None)
            if kp:
                cells.append(MatrixCell(True, kp.watch_out, kp.detail[:120]))
            else:
                cells.append(MatrixCell(False, False, "Not mentioned"))
        rows.append(CategoryRow(cat, icon, cells))

    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Recommendation text
# ─────────────────────────────────────────────────────────────────────────────

def _build_recommendation(rankings: List[DocRanking]) -> tuple:
    """Returns (winner_reason, recommendation)."""
    best = rankings[0]
    worst = rankings[-1]
    n = len(rankings)

    # Why best won
    reason_parts = []
    if best.result.risk_score < 30:
        reason_parts.append(f"low risk score of {best.result.risk_score}/100")
    if not best.result.red_flags:
        reason_parts.append("no red flags")
    elif len(best.result.red_flags) < len(worst.result.red_flags):
        reason_parts.append(f"fewest red flags ({len(best.result.red_flags)})")
    if best.watch_count == 0:
        reason_parts.append("no concerning clauses")

    if reason_parts:
        winner_reason = f"Ranked #1 due to its {', '.join(reason_parts)}."
    else:
        winner_reason = f"Ranked #1 with the lowest composite risk score among all {n} documents."

    # Full recommendation
    score_gap = worst.result.risk_score - best.result.risk_score
    if score_gap >= 30:
        strength = "significantly"
    elif score_gap >= 15:
        strength = "meaningfully"
    else:
        strength = "slightly"

    rec = (
        f"Based on the analysis of {n} documents, "
        f"<strong>{best.name}</strong> is {strength} the safest choice. "
    )

    if best.strengths:
        rec += f"It stands out for: {best.strengths[0].lower()}. "

    if n > 2 and len(rankings) > 1:
        second = rankings[1]
        if second.total_score - best.total_score < 5:
            rec += f"{second.name} is a close second and also a reasonable option. "

    if worst.result.red_flags:
        rec += (
            f"Avoid <strong>{worst.name}</strong> if possible — it carries "
            f"{len(worst.result.red_flags)} red flag(s) and scored {worst.result.risk_score}/100 on risk."
        )

    return winner_reason, rec


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def multi_compare(doc_pairs: list) -> MultiCompareResult:
    """
    Rank and compare N documents.

    doc_pairs: [(name: str, result: AnalysisResult), ...]
               Must have at least 2 items; ideally 3–8.
    """
    if len(doc_pairs) < 2:
        raise ValueError("Need at least 2 documents to compare.")

    # Score and rank
    scored = [
        (name, result, _composite_score(result))
        for name, result in doc_pairs
    ]
    scored.sort(key=lambda x: x[2])   # ascending — lower score = safer = better rank

    rankings: List[DocRanking] = []
    for rank, (name, result, score) in enumerate(scored, 1):
        watch_count = sum(1 for kp in result.key_points if kp.watch_out)
        rankings.append(DocRanking(
            rank=rank,
            name=name,
            result=result,
            total_score=round(score, 1),
            watch_count=watch_count,
            strengths=_strengths(name, result, [(n, r) for n, r, _ in scored]),
            weaknesses=_weaknesses(name, result, [(n, r) for n, r, _ in scored]),
        ))

    ranked_names = [r.name for r in rankings]
    matrix       = _build_matrix(doc_pairs, ranked_names)
    winner_reason, recommendation = _build_recommendation(rankings)

    return MultiCompareResult(
        doc_names=ranked_names,
        rankings=rankings,
        matrix=matrix,
        winner_name=rankings[0].name,
        winner_reason=winner_reason,
        recommendation=recommendation,
    )
