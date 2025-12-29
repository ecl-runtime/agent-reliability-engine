from dataclasses import dataclass
from typing import Dict, List, Any
from datetime import datetime, timedelta
import hashlib

@dataclass
class GateDecision:
    allowed: bool
    reason: str
    gates_passed: List[str]
    gates_failed: List[str]
    risk_score: float
    human_review_required: bool
    override_price: float
    audit_id: str
    telemetry: Dict[str, Any]

class AgentReliabilityEngine:
    GATE_WEIGHTS = {
        "intent_clear": 0.15,
        "state_fresh": 0.25,
        "blast_bounded": 0.30,
        "reversible": 0.20,
        "reasoning_valid": 0.10
    }
    HARD_BLOCK_GATES = ["blast_bounded", "reversible"]
    
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.state_cache: Dict[str, Dict] = {}
        self.state_freshness_threshold = timedelta(seconds=30)
        self.audit_log = []
    
    def update_state(self, key: str, value: Any):
        """Agents refresh state through ARE"""
        self.state_cache[key] = {
            "value": value,
            "timestamp": datetime.now()
        }
    
    def can_execute(self, action: str, params: Dict[str, Any], 
                   reasoning: str, state_deps: List[str]) -> GateDecision:
        """The single gate all agents call before acting."""
        
        gates = [
            ("intent_clear", self._check_intent_clarity(action, reasoning)),
            ("state_fresh", self._check_state_freshness(state_deps)),
            ("blast_bounded", self._check_blast_radius(action, params)),
            ("reversible", self._check_reversibility(action)),
            ("reasoning_valid", self._check_reasoning_quality(reasoning))
        ]
        
        failed_gates = [g for g in gates if not g]
        passed_gates = [g for g in gates if g]
        
        total_risk = sum(self.GATE_WEIGHTS.get(name, 0) for name, passed in gates if not passed)
        hard_blocked = any(not passed for name, passed in gates if name in self.HARD_BLOCK_GATES)
        
        allowed = not hard_blocked and total_risk < 0.25
        human_review = total_risk > 0.15 or hard_blocked
        
        override_price = 5.0 if total_risk > 0.5 else 0.0
        
        audit_id = hashlib.sha256(
            f"{self.agent_id}:{action}:{datetime.now().isoformat()}".encode()
        ).hexdigest()[:8]
        
        reason = self._generate_reason(gates, total_risk)
        
        decision = GateDecision(
            allowed=allowed,
            reason=reason,
            gates_passed=passed_gates,
            gates_failed=failed_gates,
            risk_score=total_risk,
            human_review_required=human_review,
            override_price=override_price,
            audit_id=audit_id,
            telemetry={
                "timestamp": datetime.now().isoformat(),
                "agent_id": self.agent_id,
                "action": action,
                "gates": {name: passed for name, passed in gates}
            }
        )
        
        self.audit_log.append(decision)
        return decision
    
    def _check_intent_clarity(self, action: str, reasoning: str) -> bool:
        """Specific action + reasoning vs vague/black-box"""
        vague_patterns = ["do the thing", "handle it", "process", "update"]
        if any(pattern in action.lower() or pattern in reasoning.lower() 
               for pattern in vague_patterns):
            return False
        return len(reasoning) > 20 and len(action) > 5
    
    def _check_state_freshness(self, state_deps: List[str]) -> bool:
        """All state dependencies must be fresh"""
        for dep in state_deps:
            if dep not in self.state_cache:
                return False
            if datetime.now() - self.state_cache[dep]["timestamp"] > self.state_freshness_threshold:
                return False
        return True
    
    def _check_blast_radius(self, action: str, params: Dict[str, Any]) -> bool:
        """Must affect bounded scope"""
        risky_actions = ["bulk", "all", "delete_all", "refund_all"]
        return not any(pattern in action.lower() for pattern in risky_actions)
    
    def _check_reversibility(self, action: str) -> bool:
        """Known reversible actions"""
        irreversible = ["delete_permanently", "drop_table", "hard_delete"]
        return not any(pattern in action.lower() for pattern in irreversible)
    
    def _check_reasoning_quality(self, reasoning: str) -> bool:
        """Must contain causal explanation"""
        good_indicators = ["because", "since", "due to"]
        return any(indicator in reasoning.lower() for indicator in good_indicators)
    
    def _generate_reason(self, gates: List, total_risk: float) -> str:
        """Generate human-readable reason"""
        failed = [g for g in gates if not g]
        if failed:
            return f"BLOCKED: {', '.join(failed)} - Risk score: {total_risk:.1%}"
        return f"ALLOWED - Risk score: {total_risk:.1%}"

