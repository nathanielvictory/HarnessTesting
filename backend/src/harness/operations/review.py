from enum import StrEnum

from harness.graph.state import Node
from harness.graph.traverser import Outcome


class ReviewDecision(StrEnum):
    ACCEPT = "accept"
    FEEDBACK = "feedback"
    REVISE = "revise"
    REVIEW_EARLIER = "review_earlier"
    RETURN = "return"


def record_review(node: Node, target: Node, decision: ReviewDecision, note: str = "") -> Outcome:
    evidence = {"target_id": target.id, "note": note}
    if target.commit_sha is not None:
        evidence["reviewed_commit_sha"] = target.commit_sha
    node.data = {**(node.data or {}), "last_decision": {"action": decision.value, **evidence}}
    return Outcome(decision.value, evidence)
