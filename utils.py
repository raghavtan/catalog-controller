from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

def get_condition(conditions: List[Dict[str, Any]], condition_type: str) -> Optional[Dict[str, Any]]:
    return next((c for c in conditions if c and c.get("type") == condition_type), None)

def set_condition(conditions: List[Dict[str, Any]], condition_type: str, status: str, reason: str, message: str):
    now = datetime.now(timezone.utc).isoformat()
    condition = get_condition(conditions, condition_type)
    if not condition:
        conditions.append({
            "type": condition_type,
            "status": status,
            "lastTransitionTime": now,
            "reason": reason,
            "message": message
        })
    else:
        condition["lastTransitionTime"] = now if condition.get("status") != status else condition["lastTransitionTime"]
        condition.update({ "status": status,"reason": reason, "message": message })
