"""Day 19 — Rich response types: Pydantic cards built from SQL rows.

Mission schemas:
  ClaimStatusCard{claim_id, status, amount, date}
  CoverageSummaryCard{plan_name, deductible, copay, covered: bool}

Design: Pydantic IS the output validator (Day-13 philosophy, applied to
outputs). A row that fails validation never becomes a card — the grounded
prose answer still covers it, so failure degrades gracefully. The builder
maps DB column names (claim_amount, date_filed, annual_deductible,
copay_pct) onto the mission's card fields.
"""
from pydantic import BaseModel, Field, ValidationError, field_validator
from typing import Literal, Optional


class ClaimStatusCard(BaseModel):
    """One claim's status — mission schema {claim_id, status, amount, date}."""
    card_type: Literal["claim_status"] = "claim_status"
    claim_id: str = Field(pattern=r"^C\d{3,}$")
    status: str = Field(min_length=1)
    amount: float = Field(ge=0)
    date: str = Field(min_length=1)

    @field_validator("status")
    @classmethod
    def normalize_status(cls, v: str) -> str:
        return v.strip().capitalize()          # approved/APPROVED -> Approved


class CoverageSummaryCard(BaseModel):
    """One plan's key numbers — mission schema
    {plan_name, deductible, copay, covered}.
    deductible/copay are Optional: Template-3 price queries SELECT only
    plan_id/plan_name/monthly_premium; the card renders '—' for the rest."""
    card_type: Literal["coverage_summary"] = "coverage_summary"
    plan_name: str = Field(min_length=1)
    deductible: Optional[float] = Field(default=None, ge=0)
    copay: Optional[float] = Field(default=None, ge=0, le=100)
    covered: bool = True          # row exists in plans table -> active coverage


STATUS_ICONS = {"Approved": "✅", "Pending": "⏳", "Denied": "❌"}
MAX_CARDS = 4          # a 3-plan comparison is useful; a wall of cards is noise


def build_cards(sql_rows: list[dict]) -> list[dict]:
    """Route SQL rows to card models by shape; return validated dicts.

    Shape detection, not table names: claim rows carry claim_id+status,
    plan rows carry plan_name. Column names -> mission field names mapped
    here. Rows failing validation are skipped, never raised — cards are
    garnish, the grounded prose answer is the meal.
    """
    cards: list[dict] = []
    for row in sql_rows:
        if len(cards) >= MAX_CARDS:
            break
        try:
            if "claim_id" in row and "status" in row:
                cards.append(ClaimStatusCard(
                    claim_id=row["claim_id"],
                    status=row["status"],
                    amount=row.get("claim_amount", 0),
                    date=str(row.get("date_filed", ""))[:10],   # trim " 00:00:00"
                ).model_dump())
            elif "plan_name" in row:
                cards.append(CoverageSummaryCard(
                    plan_name=row["plan_name"],
                    deductible=row.get("annual_deductible"),
                    copay=row.get("copay_pct"),
                ).model_dump())
        except ValidationError:
            continue
    return cards


# ---------------------------------------------------------------
# quick test — python response_cards.py
# ---------------------------------------------------------------
if __name__ == "__main__":
    good_claim = {"claim_id": "C1001", "member_id": "M1001",
                  "procedure": "X-Ray", "claim_amount": 450.0,
                  "status": "approved", "date_filed": "2026-05-14"}
    good_plan = {"plan_id": "P101", "plan_name": "Gold PPO",
                 "monthly_premium": 500.0, "annual_deductible": 2000.0,
                 "copay_pct": 10.0}
    partial_plan = {"plan_id": "P103", "plan_name": "Bronze HMO",
                    "monthly_premium": 150.0}          # Template-3 shape
    bad_claim = {"claim_id": "C-BAD!", "member_id": "M1001",
                 "procedure": "MRI", "claim_amount": -50,
                 "status": "pending", "date_filed": "2026-06-01"}

    cards = build_cards([good_claim, good_plan, partial_plan, bad_claim])
    print(f"built {len(cards)} cards from 4 rows (expect 3 — bad row rejected):\n")
    for c in cards:
        print(" ", c)

    assert len(cards) == 3, "validation gate failed"
    assert cards[0]["status"] == "Approved", "status not normalized"
    assert cards[0]["amount"] == 450.0 and cards[0]["date"] == "2026-05-14", "mapping broken"
    assert cards[2]["deductible"] is None, "optional field broken"
    assert cards[1]["covered"] is True, "covered default broken"
    print("\nall assertions passed ✓")