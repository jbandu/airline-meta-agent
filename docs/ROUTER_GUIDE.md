# Intelligent Request Router Guide

## Overview

The enhanced request router provides sophisticated orchestration of airline domain agents with LLM-powered intent classification, semantic matching, multiple execution modes, and advanced resilience patterns.

## Key Features

### 1. LLM-Powered Intent Classification

The router uses Claude AI to analyze incoming requests and extract:
- **Domain**: Primary operational domain (baggage_operations, crew_operations, etc.)
- **Intent**: What the user wants to accomplish
- **Required Capabilities**: Specific agent capabilities needed
- **Urgency Level**: high, medium, or low priority
- **Multi-Agent Flag**: Whether multiple agents are needed
- **Execution Mode**: How agents should be orchestrated

### 2. Execution Modes

#### Sequential Execution
Agents execute one after another, with context passing between them.

**Use Case**: When agents need to build on each other's results

**Example**:
```
User: "Where is bag NH459 and what's the risk it will miss the connection?"
→ baggage_tracker_agent (locate bag)
→ risk_assessment_agent (assess with location data)
→ connection_protection_agent (evaluate protection options)
```

**Response Format**:
```json
{
  "success": true,
  "message": "baggage_tracker_agent: Bag located at Gate 14 → risk_assessment_agent: High risk of missing connection → connection_protection_agent: Protection plan initiated",
  "data": {
    "baggage_tracker_agent": {...},
    "risk_assessment_agent": {...},
    "connection_protection_agent": {...}
  },
  "execution_chain": ["baggage_tracker_agent", "risk_assessment_agent", "connection_protection_agent"]
}
```

#### Parallel Execution
Agents execute simultaneously, results aggregated at the end.

**Use Case**: When agents can work independently

**Example**:
```
User: "What's causing high baggage mishandling on route PTY-MIA?"
→ analytics_agent (parallel)
→ exception_management_agent (parallel)
```

**Response Format**:
```json
{
  "success": true,
  "message": "Combined results:\n• analytics_agent: Identified 3 root causes\n• exception_management_agent: Found 15 recent exceptions",
  "data": {
    "analytics_agent": {...},
    "exception_management_agent": {...}
  },
  "agents_contributed": ["analytics_agent", "exception_management_agent"]
}
```

#### Conditional Execution
Agents execute sequentially, but only continue if previous agent succeeds.

**Use Case**: When each step depends on previous success

### 3. Semantic Matching

When exact capability matches aren't found, the router uses semantic similarity matching:

```python
# Example: Looking for "baggage_tracking"
# Will match agents with capabilities like:
# - "track"
# - "tracking"
# - "baggage_location"
```

**Similarity Threshold**: 0.7 (configurable)

### 4. Circuit Breaker Pattern

Protects against cascading failures by tracking agent errors:

- **Threshold**: 3 consecutive failures (configurable)
- **Behavior**: Agent is excluded from routing when circuit is open
- **Reset**: Automatic on successful execution, or manual via API

**Monitoring**:
```python
stats = router.get_routing_stats()
# Returns:
# {
#   "circuit_breakers_open": ["failing_agent_1"],
#   "agent_failure_counts": {"failing_agent_1": 3}
# }
```

**Manual Reset**:
```python
router.reset_circuit_breaker("agent_name")
```

### 5. Retry Logic with Exponential Backoff

Each agent execution is retried up to 3 times (configurable):

- **Attempt 1**: Immediate
- **Attempt 2**: Wait 2 seconds
- **Attempt 3**: Wait 4 seconds
- **Attempt 4**: Wait 8 seconds

**Logging**:
```json
{
  "event": "retrying_agent_execution",
  "agent": "baggage_tracker_agent",
  "wait_seconds": 2,
  "attempt": 2
}
```

### 6. Load Balancing

When multiple agents have the same capability, the router uses round-robin load balancing:

```python
# If 3 agents can handle "track" capability:
# Request 1 → agent_1
# Request 2 → agent_2
# Request 3 → agent_3
# Request 4 → agent_1 (cycles back)
```

### 7. Fallback Routing

If no agents match the required capabilities:
1. Try semantic matching (threshold 0.7)
2. If still no match, select any healthy agent from the domain
3. Log fallback attempt for analysis

**Example**:
```json
{
  "event": "fallback_agent_selected",
  "agent": "baggage_tracker_agent",
  "session_id": "abc123"
}
```

### 8. Priority Queuing by Urgency

Requests are classified by urgency:

- **High**: Time-sensitive (missing connections, urgent baggage issues)
- **Medium**: Standard requests
- **Low**: Analytics, reporting

High-urgency requests can be prioritized in queue processing.

## Routing Examples

### Example 1: Single Agent Request

**User Query**: "Validate crew member pay for trip 2847"

**Classification**:
```json
{
  "domain": "crew_operations",
  "intent": "validate crew pay",
  "required_capabilities": ["pay_validation"],
  "urgency": "medium",
  "multi_agent": false,
  "execution_mode": "sequential"
}
```

**Routing**:
- Selected: `crew_pay_validator`
- Execution: Single agent call

### Example 2: Multi-Agent Sequential

**User Query**: "Where is bag NH459 and what's the risk it will miss the connection?"

**Classification**:
```json
{
  "domain": "baggage_operations",
  "intent": "track baggage and assess connection risk",
  "required_capabilities": ["track", "locate", "risk_analysis", "connections"],
  "urgency": "high",
  "multi_agent": true,
  "execution_mode": "sequential"
}
```

**Routing**:
- Selected: `["baggage_tracker_agent", "risk_assessment_agent", "connection_protection_agent"]`
- Execution: Sequential with context passing
- Agent 1 output → Agent 2 context
- Agent 2 output → Agent 3 context

### Example 3: Multi-Agent Parallel

**User Query**: "What's causing high baggage mishandling on route PTY-MIA?"

**Classification**:
```json
{
  "domain": "baggage_operations",
  "intent": "analyze baggage mishandling root causes",
  "required_capabilities": ["analytics", "exceptions"],
  "urgency": "low",
  "multi_agent": true,
  "execution_mode": "parallel"
}
```

**Routing**:
- Selected: `["analytics_agent", "exception_management_agent"]`
- Execution: Parallel execution
- Results aggregated at the end

## Configuration

### Router Initialization

```python
router = RequestRouter(
    registry=agent_registry,
    context_manager=context_manager,
    anthropic_api_key="your_api_key",
    model="claude-3-5-sonnet-20241022",
    max_retries=3,  # Number of retry attempts
    circuit_breaker_threshold=3,  # Failures before circuit opens
)
```

### Semantic Similarity Threshold

Located in `_select_agents` method:
```python
semantic_threshold = 0.7  # Adjust for stricter/looser matching
```

## Monitoring and Logging

### Key Log Events

1. **Intent Classification**:
```json
{
  "event": "intent_classified",
  "domain": "baggage_operations",
  "intent": "track baggage",
  "urgency": "high",
  "execution_mode": "sequential"
}
```

2. **Agent Selection**:
```json
{
  "event": "agents_selected",
  "agents": ["baggage_tracker_agent"],
  "execution_mode": "sequential",
  "fallback_used": false
}
```

3. **Circuit Breaker**:
```json
{
  "event": "circuit_breaker_open",
  "agent": "failing_agent",
  "failure_count": 3
}
```

4. **Retry Logic**:
```json
{
  "event": "retrying_agent_execution",
  "agent": "baggage_tracker_agent",
  "wait_seconds": 2,
  "attempt": 2
}
```

5. **Response Aggregation**:
```json
{
  "event": "responses_aggregated",
  "successful": 3,
  "failed": 0,
  "execution_mode": "sequential",
  "urgency": "high"
}
```

### Metrics

The router integrates with Prometheus metrics:

- `orchestrator_requests_total` - Total routing requests
- `agent_requests_total{agent_name, status}` - Agent-specific requests
- `circuit_breaker_failures_total{agent_name}` - Circuit breaker triggers
- `agent_request_duration_seconds{agent_name}` - Agent latency

## Best Practices

### 1. Intent Classification Prompt Engineering

The system prompt is comprehensive but can be customized in `_classify_intent` method to:
- Add new domains
- Define new capabilities
- Adjust urgency criteria
- Modify execution mode logic

### 2. Circuit Breaker Management

- Monitor `get_routing_stats()` regularly
- Reset stuck circuit breakers manually when agents recover
- Adjust threshold based on agent reliability

### 3. Load Balancing

- Deploy multiple instances of high-traffic agents
- Monitor `agent_load_counter` for distribution
- Reset counters periodically to rebalance

### 4. Error Handling

- Always check `response.success` field
- Log all routing decisions for debugging
- Use fallback responses for critical paths

### 5. Performance Optimization

- Use `parallel` mode when agents are independent
- Limit agent chain length in sequential mode
- Set appropriate retry limits for time-sensitive requests

## Troubleshooting

### Issue: Circuit Breaker Constantly Opening

**Solution**:
- Check agent health endpoints
- Review agent logs for errors
- Increase `circuit_breaker_threshold` if transient failures
- Fix underlying agent issues

### Issue: Incorrect Agent Selection

**Solution**:
- Review intent classification logs
- Adjust semantic similarity threshold
- Update agent capability definitions
- Enhance system prompt with examples

### Issue: High Latency

**Solution**:
- Use parallel mode when possible
- Reduce retry attempts for non-critical paths
- Optimize agent response times
- Check for circuit breaker delays

### Issue: Fallback Routing Too Frequent

**Solution**:
- Review capability definitions
- Ensure agents are properly registered
- Check for typos in capability names
- Add more agents with needed capabilities

## API Reference

### Main Method

```python
async def route_request(
    session_id: str,
    user_id: str,
    message: str,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]
```

**Returns**:
```python
{
    "success": bool,
    "message": str,
    "data": Dict[str, Any],
    "agents_used": List[str],
    "intent": str,
    "urgency": str,
    "execution_mode": str,
    "fallback_used": bool,
    "total_agents_attempted": int,
    "successful_agents": int,
    "execution_chain": List[str],  # For sequential
    "agents_contributed": List[str],  # For parallel
}
```

### Helper Methods

```python
# Reset circuit breaker for specific agent
router.reset_circuit_breaker("agent_name")

# Get routing statistics
stats = router.get_routing_stats()

# Reset all circuit breakers
router.reset_all_circuit_breakers()
```

## Future Enhancements

1. **Embeddings-Based Semantic Matching**: Use vector embeddings for more accurate semantic similarity
2. **Adaptive Timeout**: Adjust timeouts based on urgency level
3. **Agent Ranking**: Score and rank agents based on historical performance
4. **Request Caching**: Cache similar requests to reduce latency
5. **A/B Testing**: Test different routing strategies
6. **ML-Based Intent Classification**: Train custom model on routing history
