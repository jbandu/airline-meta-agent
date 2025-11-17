"""Request router with LangGraph orchestration and LLM-based intent classification."""

import asyncio
import random
import time
from enum import Enum
import structlog
from typing import Any, Dict, List, Optional, TypedDict, Tuple
from langchain_anthropic import ChatAnthropic
from langchain.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END
import json
import numpy as np

from src.orchestrator.registry import AgentRegistry
from src.orchestrator.context_manager import ContextManager
from src.agents.base_agent import AgentRequest, AgentResponse
from src.monitoring.metrics import MetricsCollector

logger = structlog.get_logger()


class ExecutionMode(str, Enum):
    """Agent execution modes."""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"


class UrgencyLevel(str, Enum):
    """Request urgency levels."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RouterState(TypedDict):
    """State for the router graph."""
    session_id: str
    user_id: str
    message: str
    domain: Optional[str]
    intent: Optional[str]
    capabilities_needed: List[str]
    selected_agents: List[str]
    agent_responses: List[AgentResponse]
    final_response: Optional[Dict[str, Any]]
    context: Dict[str, Any]
    urgency: Optional[str]
    execution_mode: Optional[str]
    multi_agent: bool
    retry_count: int
    fallback_attempted: bool


class RequestRouter:
    """Intelligent router using LangGraph and LLM for intent classification."""

    def __init__(
        self,
        registry: AgentRegistry,
        context_manager: ContextManager,
        anthropic_api_key: str,
        model: str = "claude-3-5-sonnet-20241022",
        max_retries: int = 3,
        circuit_breaker_threshold: int = 3,
    ):
        self.registry = registry
        self.context_manager = context_manager
        self.llm = ChatAnthropic(
            model=model,
            temperature=0.1,
            api_key=anthropic_api_key,
        )
        self.max_retries = max_retries
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.agent_failure_counts: Dict[str, int] = {}
        self.agent_load_counter: Dict[str, int] = {}
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(RouterState)

        # Add nodes
        workflow.add_node("classify_intent", self._classify_intent)
        workflow.add_node("select_agents", self._select_agents)
        workflow.add_node("execute_agents", self._execute_agents)
        workflow.add_node("aggregate_responses", self._aggregate_responses)

        # Add edges
        workflow.set_entry_point("classify_intent")
        workflow.add_edge("classify_intent", "select_agents")
        workflow.add_edge("select_agents", "execute_agents")
        workflow.add_edge("execute_agents", "aggregate_responses")
        workflow.add_edge("aggregate_responses", END)

        return workflow.compile()

    async def route_request(
        self,
        session_id: str,
        user_id: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Route a request through the agent workflow."""
        initial_state: RouterState = {
            "session_id": session_id,
            "user_id": user_id,
            "message": message,
            "domain": None,
            "intent": None,
            "capabilities_needed": [],
            "selected_agents": [],
            "agent_responses": [],
            "final_response": None,
            "context": context or {},
            "urgency": None,
            "execution_mode": None,
            "multi_agent": False,
            "retry_count": 0,
            "fallback_attempted": False,
        }

        routing_start_time = time.time()

        try:
            result = await self.graph.ainvoke(initial_state)

            routing_duration = (time.time() - routing_start_time) * 1000

            logger.info(
                "routing_complete",
                session_id=session_id,
                agents_used=result.get("selected_agents", []),
                execution_mode=result.get("execution_mode"),
                urgency=result.get("urgency"),
                duration_ms=routing_duration,
            )

            return result.get("final_response", {})

        except Exception as e:
            logger.error(
                "routing_error",
                session_id=session_id,
                error=str(e),
            )
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to process request",
            }

    async def _classify_intent(self, state: RouterState) -> RouterState:
        """Classify user intent and determine domain with enhanced analysis."""
        logger.info("classifying_intent", session_id=state["session_id"])

        # Get available domains and capabilities
        domains = self.registry.list_domains()
        capabilities = self.registry.list_capabilities()

        # Get agent registry info for better context
        agents_info = []
        for agent in self.registry.get_all_agents():
            agents_info.append({
                "name": agent.metadata.name,
                "domain": agent.metadata.domain,
                "capabilities": agent.metadata.capabilities,
                "description": agent.metadata.description,
            })

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert airline operations AI assistant. Analyze the incoming query and classify it precisely.

Available domains: {domains}
Available capabilities: {capabilities}

Available agents:
{agents_info}

Analyze this airline operations query and return JSON with the following structure:
{{
  "domain": "baggage_operations|crew_operations|flight_ops",
  "intent": "brief description of what user wants",
  "required_capabilities": ["capability1", "capability2"],
  "urgency": "high|medium|low",
  "multi_agent": true|false,
  "execution_mode": "sequential|parallel|conditional",
  "reasoning": "brief explanation of routing decision"
}}

Guidelines:
- "urgency": Set to "high" for time-sensitive issues (missing connections, urgent baggage issues), "medium" for standard requests, "low" for analytics/reporting
- "multi_agent": Set to true if multiple agents needed to fully answer the query
- "execution_mode":
  * "sequential" - when agents need to build on each other's results (e.g., track baggage → assess risk → plan recovery)
  * "parallel" - when agents can work independently and results aggregated (e.g., analytics from multiple sources)
  * "conditional" - when next agent depends on previous agent's results

Examples:

Query: "Where is bag NH459 and what's the risk it will miss the connection?"
Response: {{
  "domain": "baggage_operations",
  "intent": "track baggage and assess connection risk",
  "required_capabilities": ["track", "locate", "risk_analysis", "connections"],
  "urgency": "high",
  "multi_agent": true,
  "execution_mode": "sequential",
  "reasoning": "Need to first locate bag, then assess risk with that location data, then evaluate connection protection"
}}

Query: "Validate crew member pay for trip 2847"
Response: {{
  "domain": "crew_operations",
  "intent": "validate crew pay",
  "required_capabilities": ["pay_validation"],
  "urgency": "medium",
  "multi_agent": false,
  "execution_mode": "sequential",
  "reasoning": "Single agent can handle pay validation"
}}

Query: "What's causing high baggage mishandling on route PTY-MIA?"
Response: {{
  "domain": "baggage_operations",
  "intent": "analyze baggage mishandling root causes",
  "required_capabilities": ["analytics", "exceptions"],
  "urgency": "low",
  "multi_agent": true,
  "execution_mode": "parallel",
  "reasoning": "Analytics and exception data can be gathered in parallel then combined"
}}

Now analyze the user's query."""),
            ("human", "{message}"),
        ])

        try:
            chain = prompt | self.llm
            response = await chain.ainvoke({
                "message": state["message"],
                "domains": ", ".join(domains),
                "capabilities": ", ".join(capabilities),
                "agents_info": json.dumps(agents_info, indent=2),
            })

            # Parse LLM response
            content = response.content
            # Extract JSON from response
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                json_str = content.strip()

            classification = json.loads(json_str)

            state["domain"] = classification.get("domain", "baggage_operations")
            state["intent"] = classification.get("intent", "")
            state["capabilities_needed"] = classification.get("required_capabilities", [])
            state["urgency"] = classification.get("urgency", "medium")
            state["multi_agent"] = classification.get("multi_agent", False)
            state["execution_mode"] = classification.get("execution_mode", "sequential")

            logger.info(
                "intent_classified",
                session_id=state["session_id"],
                domain=state["domain"],
                intent=state["intent"],
                capabilities=state["capabilities_needed"],
                urgency=state["urgency"],
                multi_agent=state["multi_agent"],
                execution_mode=state["execution_mode"],
                reasoning=classification.get("reasoning", ""),
            )

        except Exception as e:
            logger.error(
                "intent_classification_error",
                session_id=state["session_id"],
                error=str(e),
            )
            # Fallback to default classification
            state["domain"] = "baggage_operations"
            state["capabilities_needed"] = ["track"]
            state["urgency"] = "medium"
            state["multi_agent"] = False
            state["execution_mode"] = "sequential"

        return state

    def _calculate_semantic_similarity(
        self, capability: str, agent_capabilities: List[str]
    ) -> float:
        """
        Calculate semantic similarity between capability and agent capabilities.
        Using simple overlap for now. Can be enhanced with embeddings.
        """
        if capability in agent_capabilities:
            return 1.0

        # Simple keyword matching
        capability_words = set(capability.lower().split("_"))
        max_similarity = 0.0

        for agent_cap in agent_capabilities:
            agent_cap_words = set(agent_cap.lower().split("_"))
            overlap = len(capability_words & agent_cap_words)
            if overlap > 0:
                similarity = overlap / max(len(capability_words), len(agent_cap_words))
                max_similarity = max(max_similarity, similarity)

        return max_similarity

    def _is_circuit_breaker_open(self, agent_name: str) -> bool:
        """Check if circuit breaker is open for an agent."""
        failure_count = self.agent_failure_counts.get(agent_name, 0)
        is_open = failure_count >= self.circuit_breaker_threshold

        if is_open:
            logger.warning(
                "circuit_breaker_open",
                agent=agent_name,
                failure_count=failure_count,
            )
            MetricsCollector.record_circuit_breaker_failure(agent_name)

        return is_open

    def _select_agent_with_load_balancing(
        self, candidates: List[str]
    ) -> Optional[str]:
        """Select agent using round-robin load balancing."""
        if not candidates:
            return None

        # Filter out agents with open circuit breakers
        available = [a for a in candidates if not self._is_circuit_breaker_open(a)]

        if not available:
            logger.warning("no_agents_available_after_circuit_breaker_check")
            return None

        # Round-robin selection
        load_counts = [(a, self.agent_load_counter.get(a, 0)) for a in available]
        selected = min(load_counts, key=lambda x: x[1])[0]

        # Increment load counter
        self.agent_load_counter[selected] = self.agent_load_counter.get(selected, 0) + 1

        return selected

    async def _select_agents(self, state: RouterState) -> RouterState:
        """Select appropriate agents based on capabilities with intelligent matching."""
        logger.info(
            "selecting_agents",
            session_id=state["session_id"],
            urgency=state["urgency"],
        )

        selected_agents_map: Dict[str, List[str]] = {}  # capability -> [agents]
        semantic_threshold = 0.7

        # For each required capability, find matching agents
        for capability in state["capabilities_needed"]:
            candidate_agents = []

            # First, try exact capability match
            agents = self.registry.get_agents_by_capability(capability)

            for agent in agents:
                # Only consider healthy agents
                if agent.metadata.status.value != "healthy":
                    continue

                # Check circuit breaker
                if self._is_circuit_breaker_open(agent.metadata.name):
                    continue

                candidate_agents.append(agent.metadata.name)

            # If no exact matches, try semantic matching
            if not candidate_agents:
                logger.info(
                    "attempting_semantic_match",
                    capability=capability,
                    session_id=state["session_id"],
                )

                all_agents = self.registry.get_all_agents()
                for agent in all_agents:
                    if agent.metadata.status.value != "healthy":
                        continue

                    if self._is_circuit_breaker_open(agent.metadata.name):
                        continue

                    similarity = self._calculate_semantic_similarity(
                        capability, agent.metadata.capabilities
                    )

                    if similarity >= semantic_threshold:
                        candidate_agents.append(agent.metadata.name)
                        logger.info(
                            "semantic_match_found",
                            agent=agent.metadata.name,
                            capability=capability,
                            similarity=similarity,
                        )

            # Select best agent using load balancing
            if candidate_agents:
                selected = self._select_agent_with_load_balancing(candidate_agents)
                if selected:
                    selected_agents_map[capability] = [selected]

        # Flatten to unique list of agents
        selected_agents = list(set(
            agent for agents in selected_agents_map.values() for agent in agents
        ))

        # Fallback routing if no agents selected
        if not selected_agents and state["domain"]:
            logger.warning(
                "no_agents_found_attempting_fallback",
                session_id=state["session_id"],
                domain=state["domain"],
            )

            state["fallback_attempted"] = True

            # Try to get any healthy agent from the domain
            agents = self.registry.get_agents_by_domain(state["domain"])
            for agent in agents:
                if (agent.metadata.status.value == "healthy" and
                    not self._is_circuit_breaker_open(agent.metadata.name)):
                    selected_agents.append(agent.metadata.name)
                    logger.info(
                        "fallback_agent_selected",
                        agent=agent.metadata.name,
                        session_id=state["session_id"],
                    )
                    break

        # Order agents based on execution mode
        if state["execution_mode"] == ExecutionMode.SEQUENTIAL:
            # Order agents in a logical sequence based on capabilities
            ordered_agents = self._order_agents_for_sequential(
                selected_agents, state["capabilities_needed"]
            )
            state["selected_agents"] = ordered_agents
        else:
            state["selected_agents"] = selected_agents

        logger.info(
            "agents_selected",
            session_id=state["session_id"],
            agents=state["selected_agents"],
            execution_mode=state["execution_mode"],
            fallback_used=state["fallback_attempted"],
        )

        return state

    def _order_agents_for_sequential(
        self, agents: List[str], capabilities: List[str]
    ) -> List[str]:
        """Order agents for sequential execution based on capability order."""
        # Create a mapping of capability to agent
        capability_to_agent = {}

        for capability in capabilities:
            for agent_name in agents:
                agent = self.registry.get_agent(agent_name)
                if agent and capability in agent.metadata.capabilities:
                    if capability not in capability_to_agent:
                        capability_to_agent[capability] = agent_name

        # Order agents based on capability order
        ordered = []
        for capability in capabilities:
            if capability in capability_to_agent:
                agent = capability_to_agent[capability]
                if agent not in ordered:
                    ordered.append(agent)

        # Add any remaining agents
        for agent in agents:
            if agent not in ordered:
                ordered.append(agent)

        return ordered

    async def _execute_agent_with_retry(
        self,
        agent_name: str,
        request: AgentRequest,
        max_retries: Optional[int] = None,
    ) -> AgentResponse:
        """Execute agent with exponential backoff retry logic."""
        if max_retries is None:
            max_retries = self.max_retries

        agent = self.registry.get_agent(agent_name)
        if not agent:
            return AgentResponse(
                agent_name=agent_name,
                success=False,
                error=f"Agent {agent_name} not found in registry",
            )

        last_error = None

        for attempt in range(max_retries + 1):
            try:
                # Execute agent
                response = await agent.execute(request)

                # Track success/failure for circuit breaker
                if response.success:
                    # Reset failure count on success
                    self.agent_failure_counts[agent_name] = 0
                    logger.info(
                        "agent_execution_success",
                        agent=agent_name,
                        attempt=attempt + 1,
                        session_id=request.session_id,
                    )
                else:
                    # Increment failure count
                    self.agent_failure_counts[agent_name] = (
                        self.agent_failure_counts.get(agent_name, 0) + 1
                    )
                    logger.warning(
                        "agent_execution_failed",
                        agent=agent_name,
                        attempt=attempt + 1,
                        error=response.error,
                    )

                return response

            except Exception as e:
                last_error = str(e)

                # Increment failure count
                self.agent_failure_counts[agent_name] = (
                    self.agent_failure_counts.get(agent_name, 0) + 1
                )

                logger.error(
                    "agent_execution_exception",
                    agent=agent_name,
                    attempt=attempt + 1,
                    error=str(e),
                )

                # Don't retry on last attempt
                if attempt < max_retries:
                    # Exponential backoff: 2^attempt seconds
                    wait_time = 2 ** attempt
                    logger.info(
                        "retrying_agent_execution",
                        agent=agent_name,
                        wait_seconds=wait_time,
                        attempt=attempt + 1,
                    )
                    await asyncio.sleep(wait_time)

        # All retries failed
        return AgentResponse(
            agent_name=agent_name,
            success=False,
            error=f"Failed after {max_retries + 1} attempts. Last error: {last_error}",
        )

    async def _execute_sequential(
        self, state: RouterState
    ) -> List[AgentResponse]:
        """Execute agents sequentially with context passing."""
        responses = []
        accumulated_context = state["context"].copy()

        for agent_name in state["selected_agents"]:
            logger.info(
                "executing_sequential_agent",
                agent=agent_name,
                session_id=state["session_id"],
            )

            request = AgentRequest(
                session_id=state["session_id"],
                user_id=state["user_id"],
                message=state["message"],
                context=accumulated_context,
            )

            response = await self._execute_agent_with_retry(agent_name, request)
            responses.append(response)

            # Pass successful response data to next agent's context
            if response.success and response.data:
                accumulated_context[f"{agent_name}_output"] = response.data

            # Save conversation
            await self.context_manager.save_conversation(
                session_id=state["session_id"],
                user_id=state["user_id"],
                agent_name=agent_name,
                user_message=state["message"],
                agent_response=response.message or "",
                metadata=response.metadata,
            )

            # Update session
            await self.context_manager.update_session(
                state["session_id"],
                agent_name=agent_name,
                context_variables=accumulated_context,
            )

        return responses

    async def _execute_parallel(
        self, state: RouterState
    ) -> List[AgentResponse]:
        """Execute agents in parallel."""
        logger.info(
            "executing_parallel_agents",
            agents=state["selected_agents"],
            session_id=state["session_id"],
        )

        # Create tasks for parallel execution
        tasks = []
        for agent_name in state["selected_agents"]:
            request = AgentRequest(
                session_id=state["session_id"],
                user_id=state["user_id"],
                message=state["message"],
                context=state["context"],
            )
            tasks.append(self._execute_agent_with_retry(agent_name, request))

        # Execute all in parallel
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to AgentResponse
        final_responses = []
        for i, response in enumerate(responses):
            if isinstance(response, Exception):
                agent_name = state["selected_agents"][i]
                final_responses.append(
                    AgentResponse(
                        agent_name=agent_name,
                        success=False,
                        error=str(response),
                    )
                )
            else:
                final_responses.append(response)

        # Save conversations
        for agent_name, response in zip(state["selected_agents"], final_responses):
            await self.context_manager.save_conversation(
                session_id=state["session_id"],
                user_id=state["user_id"],
                agent_name=agent_name,
                user_message=state["message"],
                agent_response=response.message or "" if hasattr(response, 'message') else "",
                metadata=response.metadata if hasattr(response, 'metadata') else {},
            )

            await self.context_manager.update_session(
                state["session_id"],
                agent_name=agent_name,
            )

        return final_responses

    async def _execute_conditional(
        self, state: RouterState
    ) -> List[AgentResponse]:
        """Execute agents conditionally based on previous results."""
        responses = []
        accumulated_context = state["context"].copy()

        for i, agent_name in enumerate(state["selected_agents"]):
            # Check if we should execute based on previous results
            if i > 0 and responses:
                last_response = responses[-1]
                # Only continue if previous agent succeeded
                if not last_response.success:
                    logger.info(
                        "skipping_conditional_agent",
                        agent=agent_name,
                        reason="previous_agent_failed",
                        session_id=state["session_id"],
                    )
                    break

            logger.info(
                "executing_conditional_agent",
                agent=agent_name,
                session_id=state["session_id"],
            )

            request = AgentRequest(
                session_id=state["session_id"],
                user_id=state["user_id"],
                message=state["message"],
                context=accumulated_context,
            )

            response = await self._execute_agent_with_retry(agent_name, request)
            responses.append(response)

            # Pass response data to next agent
            if response.success and response.data:
                accumulated_context[f"{agent_name}_output"] = response.data

            # Save conversation
            await self.context_manager.save_conversation(
                session_id=state["session_id"],
                user_id=state["user_id"],
                agent_name=agent_name,
                user_message=state["message"],
                agent_response=response.message or "",
                metadata=response.metadata,
            )

            await self.context_manager.update_session(
                state["session_id"],
                agent_name=agent_name,
                context_variables=accumulated_context,
            )

        return responses

    async def _execute_agents(self, state: RouterState) -> RouterState:
        """Execute selected agents based on execution mode."""
        if not state["selected_agents"]:
            logger.warning(
                "no_agents_to_execute",
                session_id=state["session_id"],
            )
            state["agent_responses"] = []
            return state

        execution_mode = state.get("execution_mode", ExecutionMode.SEQUENTIAL)

        logger.info(
            "executing_agents",
            session_id=state["session_id"],
            agents=state["selected_agents"],
            execution_mode=execution_mode,
            urgency=state["urgency"],
        )

        # Route to appropriate execution strategy
        if execution_mode == ExecutionMode.PARALLEL:
            responses = await self._execute_parallel(state)
        elif execution_mode == ExecutionMode.CONDITIONAL:
            responses = await self._execute_conditional(state)
        else:  # SEQUENTIAL (default)
            responses = await self._execute_sequential(state)

        state["agent_responses"] = responses

        logger.info(
            "agents_executed",
            session_id=state["session_id"],
            response_count=len(responses),
            successful=sum(1 for r in responses if r.success),
            failed=sum(1 for r in responses if not r.success),
        )

        return state

    def _aggregate_sequential_responses(
        self, responses: List[AgentResponse]
    ) -> Dict[str, Any]:
        """Aggregate responses from sequential execution."""
        # In sequential mode, the last successful response is usually the most relevant
        successful_responses = [r for r in responses if r.success]

        if not successful_responses:
            return {}

        # Build a narrative from the agent chain
        narrative_parts = []
        aggregated_data = {}

        for i, response in enumerate(successful_responses):
            if response.message:
                narrative_parts.append(f"{response.agent_name}: {response.message}")

            if response.data:
                aggregated_data[response.agent_name] = response.data

        # The final message should synthesize the chain
        if narrative_parts:
            final_message = " → ".join(narrative_parts)
        else:
            final_message = successful_responses[-1].message or "Request processed successfully"

        return {
            "message": final_message,
            "data": aggregated_data,
            "execution_chain": [r.agent_name for r in successful_responses],
        }

    def _aggregate_parallel_responses(
        self, responses: List[AgentResponse]
    ) -> Dict[str, Any]:
        """Aggregate responses from parallel execution."""
        successful_responses = [r for r in responses if r.success]

        if not successful_responses:
            return {}

        # Combine data from all agents
        aggregated_data = {}
        message_parts = []

        for response in successful_responses:
            if response.data:
                aggregated_data[response.agent_name] = response.data

            if response.message:
                message_parts.append(f"• {response.agent_name}: {response.message}")

        # Create a summary message
        if message_parts:
            final_message = "Combined results:\n" + "\n".join(message_parts)
        else:
            final_message = f"Data collected from {len(successful_responses)} agents"

        return {
            "message": final_message,
            "data": aggregated_data,
            "agents_contributed": [r.agent_name for r in successful_responses],
        }

    async def _aggregate_responses(self, state: RouterState) -> RouterState:
        """Aggregate responses from multiple agents with intelligent combining."""
        logger.info("aggregating_responses", session_id=state["session_id"])

        if not state["agent_responses"]:
            state["final_response"] = {
                "success": False,
                "message": "No agents available to handle this request",
                "agents_used": [],
                "execution_mode": state.get("execution_mode"),
            }
            return state

        # Combine successful responses
        successful_responses = [
            r for r in state["agent_responses"] if r.success
        ]

        if not successful_responses:
            # All agents failed
            errors = [r.error for r in state["agent_responses"] if r.error]
            state["final_response"] = {
                "success": False,
                "message": "All agents failed to process request",
                "errors": errors,
                "agents_used": state["selected_agents"],
                "execution_mode": state.get("execution_mode"),
            }
            return state

        # Aggregate based on execution mode
        execution_mode = state.get("execution_mode", ExecutionMode.SEQUENTIAL)

        if execution_mode == ExecutionMode.PARALLEL:
            aggregation = self._aggregate_parallel_responses(successful_responses)
        else:  # SEQUENTIAL or CONDITIONAL
            aggregation = self._aggregate_sequential_responses(successful_responses)

        # Build final response
        state["final_response"] = {
            "success": True,
            "message": aggregation.get("message", "Request processed successfully"),
            "data": aggregation.get("data", {}),
            "agents_used": [r.agent_name for r in successful_responses],
            "intent": state["intent"],
            "urgency": state["urgency"],
            "execution_mode": execution_mode,
            "fallback_used": state.get("fallback_attempted", False),
            "total_agents_attempted": len(state["agent_responses"]),
            "successful_agents": len(successful_responses),
        }

        # Add execution chain or contributors based on mode
        if "execution_chain" in aggregation:
            state["final_response"]["execution_chain"] = aggregation["execution_chain"]
        elif "agents_contributed" in aggregation:
            state["final_response"]["agents_contributed"] = aggregation["agents_contributed"]

        logger.info(
            "responses_aggregated",
            session_id=state["session_id"],
            successful=len(successful_responses),
            failed=len(state["agent_responses"]) - len(successful_responses),
            execution_mode=execution_mode,
            urgency=state["urgency"],
        )

        return state

    def reset_circuit_breaker(self, agent_name: str):
        """Manually reset circuit breaker for an agent."""
        if agent_name in self.agent_failure_counts:
            del self.agent_failure_counts[agent_name]
            logger.info("circuit_breaker_reset", agent=agent_name)

    def get_routing_stats(self) -> Dict[str, Any]:
        """Get routing statistics for monitoring."""
        return {
            "agent_failure_counts": self.agent_failure_counts.copy(),
            "agent_load_counter": self.agent_load_counter.copy(),
            "circuit_breakers_open": [
                agent for agent, count in self.agent_failure_counts.items()
                if count >= self.circuit_breaker_threshold
            ],
        }

    def reset_all_circuit_breakers(self):
        """Reset all circuit breakers (use with caution)."""
        self.agent_failure_counts.clear()
        logger.info("all_circuit_breakers_reset")
