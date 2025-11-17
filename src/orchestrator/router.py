"""Request router with LangGraph orchestration and LLM-based intent classification."""

import structlog
from typing import Any, Dict, List, Optional, TypedDict
from langchain_anthropic import ChatAnthropic
from langchain.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END
import json

from src.orchestrator.registry import AgentRegistry
from src.orchestrator.context_manager import ContextManager
from src.agents.base_agent import AgentRequest, AgentResponse

logger = structlog.get_logger()


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


class RequestRouter:
    """Intelligent router using LangGraph and LLM for intent classification."""

    def __init__(
        self,
        registry: AgentRegistry,
        context_manager: ContextManager,
        anthropic_api_key: str,
        model: str = "claude-3-5-sonnet-20241022",
    ):
        self.registry = registry
        self.context_manager = context_manager
        self.llm = ChatAnthropic(
            model=model,
            temperature=0.1,
            api_key=anthropic_api_key,
        )
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
        }

        try:
            result = await self.graph.ainvoke(initial_state)

            logger.info(
                "routing_complete",
                session_id=session_id,
                agents_used=result.get("selected_agents", []),
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
        """Classify user intent and determine domain."""
        logger.info("classifying_intent", session_id=state["session_id"])

        # Get available domains and capabilities
        domains = self.registry.list_domains()
        capabilities = self.registry.list_capabilities()

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an airline operations AI assistant. Analyze the user's message and classify it.

Available domains: {domains}
Available capabilities: {capabilities}

Respond with JSON containing:
- domain: the primary domain (baggage_operations or crew_operations)
- intent: brief description of what the user wants
- capabilities_needed: list of capabilities required to fulfill the request

Example response:
{{
  "domain": "baggage_operations",
  "intent": "track lost baggage",
  "capabilities_needed": ["track", "locate"]
}}"""),
            ("human", "{message}"),
        ])

        try:
            chain = prompt | self.llm
            response = await chain.ainvoke({
                "message": state["message"],
                "domains": ", ".join(domains),
                "capabilities": ", ".join(capabilities),
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

            state["domain"] = classification.get("domain")
            state["intent"] = classification.get("intent")
            state["capabilities_needed"] = classification.get("capabilities_needed", [])

            logger.info(
                "intent_classified",
                session_id=state["session_id"],
                domain=state["domain"],
                intent=state["intent"],
                capabilities=state["capabilities_needed"],
            )

        except Exception as e:
            logger.error(
                "intent_classification_error",
                session_id=state["session_id"],
                error=str(e),
            )
            # Fallback to baggage_operations
            state["domain"] = "baggage_operations"
            state["capabilities_needed"] = ["track"]

        return state

    async def _select_agents(self, state: RouterState) -> RouterState:
        """Select appropriate agents based on capabilities."""
        logger.info("selecting_agents", session_id=state["session_id"])

        selected_agents = set()

        # Get agents by capabilities
        for capability in state["capabilities_needed"]:
            agents = self.registry.get_agents_by_capability(capability)
            for agent in agents:
                # Only select healthy agents
                if agent.metadata.status.value == "healthy":
                    selected_agents.add(agent.metadata.name)

        # If no agents found by capability, get agents by domain
        if not selected_agents and state["domain"]:
            agents = self.registry.get_agents_by_domain(state["domain"])
            for agent in agents:
                if agent.metadata.status.value == "healthy":
                    selected_agents.add(agent.metadata.name)
                    break  # Just take the first healthy agent in domain

        state["selected_agents"] = list(selected_agents)

        logger.info(
            "agents_selected",
            session_id=state["session_id"],
            agents=state["selected_agents"],
        )

        return state

    async def _execute_agents(self, state: RouterState) -> RouterState:
        """Execute selected agents."""
        logger.info(
            "executing_agents",
            session_id=state["session_id"],
            agents=state["selected_agents"],
        )

        responses = []

        for agent_name in state["selected_agents"]:
            agent = self.registry.get_agent(agent_name)
            if not agent:
                continue

            request = AgentRequest(
                session_id=state["session_id"],
                user_id=state["user_id"],
                message=state["message"],
                context=state["context"],
            )

            response = await agent.execute(request)
            responses.append(response)

            # Update context with agent in chain
            await self.context_manager.update_session(
                state["session_id"],
                agent_name=agent_name,
            )

            # Save conversation
            await self.context_manager.save_conversation(
                session_id=state["session_id"],
                user_id=state["user_id"],
                agent_name=agent_name,
                user_message=state["message"],
                agent_response=response.message or "",
                metadata=response.metadata,
            )

        state["agent_responses"] = responses

        logger.info(
            "agents_executed",
            session_id=state["session_id"],
            response_count=len(responses),
        )

        return state

    async def _aggregate_responses(self, state: RouterState) -> RouterState:
        """Aggregate responses from multiple agents."""
        logger.info("aggregating_responses", session_id=state["session_id"])

        if not state["agent_responses"]:
            state["final_response"] = {
                "success": False,
                "message": "No agents available to handle this request",
                "agents_used": [],
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
            }
            return state

        # Aggregate data from successful responses
        aggregated_data = {}
        for response in successful_responses:
            if response.data:
                aggregated_data[response.agent_name] = response.data

        # Get the primary response message
        primary_message = successful_responses[0].message or "Request processed successfully"

        state["final_response"] = {
            "success": True,
            "message": primary_message,
            "data": aggregated_data,
            "agents_used": [r.agent_name for r in successful_responses],
            "intent": state["intent"],
        }

        logger.info(
            "responses_aggregated",
            session_id=state["session_id"],
            successful=len(successful_responses),
            failed=len(state["agent_responses"]) - len(successful_responses),
        )

        return state
