# Router Examples

## Example 1: Sequential Multi-Agent Workflow

### Request
```json
{
  "message": "Where is bag NH459 and what's the risk it will miss the connection?"
}
```

### Intent Classification
```json
{
  "domain": "baggage_operations",
  "intent": "track baggage and assess connection risk",
  "required_capabilities": ["track", "locate", "risk_analysis", "connections"],
  "urgency": "high",
  "multi_agent": true,
  "execution_mode": "sequential",
  "reasoning": "Need to first locate bag, then assess risk with that location data, then evaluate connection protection"
}
```

### Agent Selection
```python
selected_agents = [
    "baggage_tracker_agent",      # Has "track" and "locate"
    "risk_assessment_agent",      # Has "risk_analysis"
    "connection_protection_agent" # Has "connections"
]
```

### Execution Flow
```
1. baggage_tracker_agent.execute()
   Input: { message: "Where is bag NH459...", context: {} }
   Output: { success: true, data: { bag_id: "NH459", location: "Gate 14", status: "in_transit" } }

2. risk_assessment_agent.execute()
   Input: {
     message: "Where is bag NH459...",
     context: {
       baggage_tracker_agent_output: { bag_id: "NH459", location: "Gate 14", status: "in_transit" }
     }
   }
   Output: { success: true, data: { risk_level: "high", time_to_connection: 15, probability_miss: 0.75 } }

3. connection_protection_agent.execute()
   Input: {
     message: "Where is bag NH459...",
     context: {
       baggage_tracker_agent_output: {...},
       risk_assessment_agent_output: { risk_level: "high", time_to_connection: 15, probability_miss: 0.75 }
     }
   }
   Output: { success: true, data: { protection_plan: "expedite", gate_hold_time: 5 } }
```

### Final Response
```json
{
  "success": true,
  "message": "baggage_tracker_agent: Bag NH459 located at Gate 14 → risk_assessment_agent: High risk (75%) of missing connection → connection_protection_agent: Expedite plan initiated with 5-minute gate hold",
  "data": {
    "baggage_tracker_agent": {
      "bag_id": "NH459",
      "location": "Gate 14",
      "status": "in_transit"
    },
    "risk_assessment_agent": {
      "risk_level": "high",
      "time_to_connection": 15,
      "probability_miss": 0.75
    },
    "connection_protection_agent": {
      "protection_plan": "expedite",
      "gate_hold_time": 5
    }
  },
  "agents_used": ["baggage_tracker_agent", "risk_assessment_agent", "connection_protection_agent"],
  "execution_chain": ["baggage_tracker_agent", "risk_assessment_agent", "connection_protection_agent"],
  "urgency": "high",
  "execution_mode": "sequential"
}
```

---

## Example 2: Parallel Multi-Agent Workflow

### Request
```json
{
  "message": "What's causing high baggage mishandling on route PTY-MIA?"
}
```

### Intent Classification
```json
{
  "domain": "baggage_operations",
  "intent": "analyze baggage mishandling root causes",
  "required_capabilities": ["analytics", "exceptions"],
  "urgency": "low",
  "multi_agent": true,
  "execution_mode": "parallel",
  "reasoning": "Analytics and exception data can be gathered in parallel then combined"
}
```

### Agent Selection
```python
selected_agents = [
    "analytics_agent",            # Has "analytics"
    "exception_management_agent"  # Has "exceptions"
]
```

### Execution Flow
```
Execute in parallel:

analytics_agent.execute() || exception_management_agent.execute()

Both receive the same input:
  { message: "What's causing...", context: {} }

Both execute independently at the same time
```

### Final Response
```json
{
  "success": true,
  "message": "Combined results:\n• analytics_agent: Identified 3 primary root causes: staff shortage (40%), system delays (35%), weather (25%)\n• exception_management_agent: Found 15 exceptions in last 24 hours, 60% during peak hours",
  "data": {
    "analytics_agent": {
      "root_causes": [
        { "cause": "staff_shortage", "percentage": 40 },
        { "cause": "system_delays", "percentage": 35 },
        { "cause": "weather", "percentage": 25 }
      ],
      "total_incidents": 42
    },
    "exception_management_agent": {
      "exceptions_24h": 15,
      "peak_hour_percentage": 60,
      "most_common_type": "delayed_transfer"
    }
  },
  "agents_used": ["analytics_agent", "exception_management_agent"],
  "agents_contributed": ["analytics_agent", "exception_management_agent"],
  "urgency": "low",
  "execution_mode": "parallel"
}
```

---

## Example 3: Single Agent

### Request
```json
{
  "message": "Validate crew member pay for trip 2847"
}
```

### Intent Classification
```json
{
  "domain": "crew_operations",
  "intent": "validate crew pay",
  "required_capabilities": ["pay_validation"],
  "urgency": "medium",
  "multi_agent": false,
  "execution_mode": "sequential",
  "reasoning": "Single agent can handle pay validation"
}
```

### Agent Selection
```python
selected_agents = ["crew_pay_validator"]
```

### Execution Flow
```
1. crew_pay_validator.execute()
   Input: { message: "Validate crew member pay for trip 2847", context: {} }
   Output: {
     success: true,
     data: {
       trip_id: "2847",
       crew_member: "CM-12345",
       hours: 8.5,
       rate: 45.00,
       total_pay: 382.50,
       validation_status: "approved"
     }
   }
```

### Final Response
```json
{
  "success": true,
  "message": "crew_pay_validator: Pay validated for trip 2847: 8.5 hours at $45/hr = $382.50 (approved)",
  "data": {
    "crew_pay_validator": {
      "trip_id": "2847",
      "crew_member": "CM-12345",
      "hours": 8.5,
      "rate": 45.00,
      "total_pay": 382.50,
      "validation_status": "approved"
    }
  },
  "agents_used": ["crew_pay_validator"],
  "execution_chain": ["crew_pay_validator"],
  "urgency": "medium",
  "execution_mode": "sequential"
}
```

---

## Example 4: Fallback Routing

### Request
```json
{
  "message": "Check baggage compliance issues"
}
```

### Intent Classification
```json
{
  "domain": "baggage_operations",
  "intent": "check compliance issues",
  "required_capabilities": ["compliance_check", "audit"],
  "urgency": "medium",
  "multi_agent": false,
  "execution_mode": "sequential"
}
```

### Agent Selection Process
```
1. Look for agents with "compliance_check" → Not found
2. Look for agents with "audit" → Not found
3. Try semantic matching:
   - "compliance_check" vs "compliance" → Similarity: 0.85 ✓
   - "audit" vs "compliance" → Similarity: 0.2 ✗
4. Select: compliance_agent
```

### Logs
```json
{
  "event": "semantic_match_found",
  "agent": "compliance_agent",
  "capability": "compliance_check",
  "similarity": 0.85
}
```

---

## Example 5: Circuit Breaker in Action

### Scenario
The `baggage_tracker_agent` has failed 3 times consecutively.

### Request
```json
{
  "message": "Track bag BA123"
}
```

### Routing Behavior
```
1. Intent classification → requires "track" capability
2. Find agents with "track" → baggage_tracker_agent
3. Check circuit breaker → OPEN (3 failures)
4. Skip baggage_tracker_agent
5. Attempt fallback → Select another agent from domain
```

### Logs
```json
[
  {
    "event": "circuit_breaker_open",
    "agent": "baggage_tracker_agent",
    "failure_count": 3
  },
  {
    "event": "fallback_agent_selected",
    "agent": "baggage_recovery_agent",
    "session_id": "abc123"
  }
]
```

---

## Example 6: Retry with Exponential Backoff

### Request
```json
{
  "message": "Locate bag XY789"
}
```

### Execution Timeline
```
00:00:00 - Attempt 1: baggage_tracker_agent.execute() → Exception: ConnectionError
00:00:00 - Wait 1 second (2^0)
00:00:01 - Attempt 2: baggage_tracker_agent.execute() → Exception: ConnectionError
00:00:01 - Wait 2 seconds (2^1)
00:00:03 - Attempt 3: baggage_tracker_agent.execute() → Exception: ConnectionError
00:00:03 - Wait 4 seconds (2^2)
00:00:07 - Attempt 4: baggage_tracker_agent.execute() → Success!
```

### Logs
```json
[
  {
    "event": "agent_execution_exception",
    "agent": "baggage_tracker_agent",
    "attempt": 1,
    "error": "ConnectionError"
  },
  {
    "event": "retrying_agent_execution",
    "agent": "baggage_tracker_agent",
    "wait_seconds": 1,
    "attempt": 1
  },
  {
    "event": "agent_execution_exception",
    "agent": "baggage_tracker_agent",
    "attempt": 2,
    "error": "ConnectionError"
  },
  {
    "event": "retrying_agent_execution",
    "agent": "baggage_tracker_agent",
    "wait_seconds": 2,
    "attempt": 2
  },
  {
    "event": "agent_execution_success",
    "agent": "baggage_tracker_agent",
    "attempt": 4
  }
]
```

---

## Example 7: Load Balancing

### Scenario
Three instances of baggage tracker deployed:
- baggage_tracker_agent_1
- baggage_tracker_agent_2
- baggage_tracker_agent_3

### Request Sequence
```
Request 1: "Track bag A1" → Routes to baggage_tracker_agent_1
Request 2: "Track bag A2" → Routes to baggage_tracker_agent_2
Request 3: "Track bag A3" → Routes to baggage_tracker_agent_3
Request 4: "Track bag A4" → Routes to baggage_tracker_agent_1 (round-robin)
Request 5: "Track bag A5" → Routes to baggage_tracker_agent_2
```

### Load Distribution
```python
router.agent_load_counter = {
    "baggage_tracker_agent_1": 2,
    "baggage_tracker_agent_2": 2,
    "baggage_tracker_agent_3": 1
}
```
