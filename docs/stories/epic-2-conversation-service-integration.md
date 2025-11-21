# Epic 2: ConversationService Integration & Hydration

## Epic Goal

Integrate the newly created TaskForce Agent Service with the existing ConversationService, enabling seamless chat-to-agent delegation, session hydration, bidirectional state synchronization, and robust error handling across the service boundary.

## Epic Description

### Existing System Context

**Current System:**
- **ConversationService**: Manages chat sessions, stores message history, handles user interactions
- **Agent Service (NEW from Epic 1)**: Standalone microservice with PostgreSQL state, SSE streaming, profile-based agent execution
- Chat frontend communicates with ConversationService via REST/WebSocket
- No existing agent delegation mechanism

**Integration Points:**
- ConversationService → Agent Service: REST API calls with SSE consumption
- Shared session concept: `conversation_id` (ConversationService) maps to `session_id` (Agent Service)
- User context: Authentication/authorization data flows from ConversationService to Agent Service
- Chat history: ConversationService owns full history, Agent Service receives windowed context

### Enhancement Details

**What's Being Added/Changed:**

This epic delivers the **integration layer** between ConversationService and Agent Service by:

1. **Agent API Client**: SDK-style client library in ConversationService for calling Agent Service
2. **Session Mapping**: Correlation between conversation sessions and agent sessions with metadata tracking
3. **History Hydration**: Intelligent chat history windowing and injection into agent execution requests
4. **SSE Consumer**: Real-time event handling to update conversation state from agent execution streams
5. **Error Handling**: Comprehensive retry logic, timeout handling, and graceful degradation
6. **End-to-End Flow**: Complete request routing from chat message → agent execution → streamed response

**How It Integrates:**

- **Client Library Pattern**: `AgentServiceClient` class abstracts REST/SSE communication
- **Message Router**: ConversationService determines when to route messages to Agent Service vs. direct LLM
- **Event Processor**: SSE events (`THOUGHT`, `TOOL_START`, `ANSWER_CHUNK`) mapped to conversation updates
- **State Synchronization**: Agent `ASK_USER` events pause execution, return control to ConversationService
- **History Compression**: Last N messages extracted from conversation and injected as `chat_history` in agent requests

**Success Criteria:**

- [ ] User sends message in chat → ConversationService routes to Agent Service → agent executes → response streams back to user
- [ ] SSE events processed in real-time and reflected in conversation UI (typing indicators, tool execution status)
- [ ] Agent `ASK_USER` events handled correctly: execution pauses, question shown to user, answer submitted back
- [ ] Session correlation works: same conversation resumes agent execution from persisted state
- [ ] Error scenarios gracefully handled: timeouts, service unavailable, stream interruption
- [ ] End-to-end latency: user sees first response chunk within 2 seconds

---

## Stories

### Story 1: Agent Service API Client Library
Create a Python client library in ConversationService that wraps Agent Service REST API calls and SSE stream handling.

**Key Deliverables:**
- `AgentServiceClient` class with methods: `execute_agent()`, `get_session_status()`
- SSE stream consumer with async iteration support
- Request/response Pydantic models matching Agent Service API contracts
- Authentication: API key injection via headers
- Connection pooling and timeout configuration
- Unit tests with mocked HTTP responses
- Retry logic with exponential backoff

### Story 2: Session Correlation & Metadata Tracking
Establish the mapping between ConversationService conversation IDs and Agent Service session IDs with bidirectional lookups.

**Key Deliverables:**
- Database schema extension: `conversation_agent_sessions` table
- Fields: `conversation_id`, `agent_session_id`, `profile_name`, `status`, `created_at`, `last_interaction_at`
- CRUD operations: create mapping, lookup session, update status
- Unique constraint: one active agent session per conversation
- Session status enum: `ACTIVE`, `AWAITING_USER`, `COMPLETED`, `FAILED`
- Database migration (Alembic or equivalent)
- Unit tests for session correlation logic

### Story 3: Chat History Extraction & Windowing
Implement intelligent history extraction from conversation to provide agent execution context without overwhelming the LLM.

**Key Deliverables:**
- `HistoryExtractor` component with windowing strategies:
  - Last N messages (default: 10)
  - Token-budget based windowing (max 4000 tokens)
  - Sliding window with summary compression
- Message format transformation: conversation schema → agent `chat_history` schema
- User context extraction: `user_id`, `org_id`, permissions from conversation metadata
- Role mapping: conversation roles → agent roles (`user`, `assistant`, `system`)
- Unit tests with various conversation lengths
- Configuration: windowing parameters adjustable via environment variables

### Story 4: Message Routing & Agent Delegation Logic
Implement the routing mechanism that determines when to delegate messages to Agent Service vs. direct LLM response.

**Key Deliverables:**
- `MessageRouter` component with routing strategies:
  - Explicit routing: user commands like `/agent` or `@agent`
  - Intent detection: keywords like "search", "analyze file", "run code"
  - Conversation context: if agent session exists, continue routing to agent
- Fallback logic: route to direct LLM if agent service unavailable
- Routing decision logging for debugging and analytics
- Configuration: enable/disable agent routing per organization or user
- Unit tests for routing scenarios
- Integration test: route message → agent service called

### Story 5: SSE Event Processor & Conversation Updates
Build the event processing pipeline that consumes Agent Service SSE streams and updates conversation state in real-time.

**Key Deliverables:**
- `AgentEventProcessor` class handling event types:
  - `THOUGHT`: Update conversation metadata (agent is thinking)
  - `TOOL_START`: Show tool execution indicator in UI
  - `TOOL_END`: Log tool result, update status
  - `ANSWER_CHUNK`: Stream response chunks to user (incremental message building)
  - `ASK_USER`: Pause execution, display question, await user input
  - `COMPLETE`: Mark agent session complete, finalize message
  - `ERROR`: Handle agent errors gracefully, show user-friendly message
- Async event handling with queue-based buffering
- Conversation database updates: append chunks to message, update status
- WebSocket fanout: push events to connected clients for real-time UI updates
- Error recovery: handle stream interruption, resume capability
- Unit tests with simulated SSE streams

### Story 6: Agent ASK_USER Workflow
Implement the full cycle for agent questions: agent asks → user sees question → user answers → answer sent back to agent → execution resumes.

**Key Deliverables:**
- `ASK_USER` event handling: extract question, create pending interaction record
- Conversation state update: mark as "awaiting user input", store question key
- UI integration: display question to user with input form
- Answer submission endpoint: POST `/conversations/{id}/agent-answer`
- Answer routing: call Agent Service `/execute` with user answer in context
- Session resumption: agent resumes from paused state
- Timeout handling: if no answer within 5 minutes, mark session as stale
- End-to-end test: agent asks → user answers → execution continues

### Story 7: Error Handling & Resilience Patterns
Implement comprehensive error handling for all failure scenarios across the service boundary.

**Key Deliverables:**
- Timeout handling:
  - Request timeout: 60 seconds for agent execution
  - Stream timeout: 5 minutes max for long-running agents
  - User response timeout: 5 minutes for `ASK_USER`
- Retry logic with exponential backoff (3 retries, 1s/2s/4s delays)
- Circuit breaker pattern: if agent service fails 5 times in 1 minute, route to direct LLM
- Graceful degradation: show cached results or "service busy" message
- Error categorization:
  - `503 Service Unavailable`: Retry with backoff
  - `408 Request Timeout`: Do not retry, inform user
  - `400 Bad Request`: Log error, show user-friendly message
  - `500 Internal Server Error`: Retry once, then fail gracefully
- Dead letter queue: failed agent requests logged for analysis
- Health check integration: ConversationService checks Agent Service `/health`
- Unit tests for each error scenario
- Load test: verify resilience under agent service degradation

### Story 8: End-to-End Integration Testing & Performance Validation
Validate the complete flow from chat message to agent execution to streamed response with performance benchmarks.

**Key Deliverables:**
- Integration test suite:
  - Happy path: user message → agent execution → complete response
  - Multi-turn: conversation with agent over 5+ exchanges
  - ASK_USER flow: agent asks question → user answers → execution continues
  - Error scenarios: service down, timeout, invalid request
  - Session resumption: restart conversation, agent resumes from saved state
- Performance tests:
  - Latency: first response chunk < 2 seconds
  - Throughput: 20 concurrent conversations with agent delegation
  - Memory: no leaks over 1000 requests
- Load test with Locust or k6:
  - 50 concurrent users
  - 10-minute duration
  - Mix: 70% direct LLM, 30% agent delegation
- Monitoring setup:
  - Metrics: request count, latency (p50/p95/p99), error rate, agent delegation rate
  - Dashboards: Grafana charts for conversation → agent flow
  - Alerts: agent service unavailable > 1 minute, error rate > 5%
- Documentation:
  - Integration architecture diagram
  - Sequence diagrams for key flows
  - Troubleshooting guide for common issues

---

## Compatibility Requirements

### API Compatibility
- [ ] Existing ConversationService endpoints unchanged (no breaking changes to chat API)
- [ ] Message schema extended (not replaced) to include agent metadata
- [ ] WebSocket protocol backward compatible (new event types added, not replaced)

### Database Compatibility
- [ ] New table `conversation_agent_sessions` does not conflict with existing schema
- [ ] Foreign key constraints to `conversations` table properly defined
- [ ] Migration reversible (rollback removes table cleanly)

### UI Compatibility
- [ ] Chat frontend works without changes (graceful degradation if new events not handled)
- [ ] New agent-specific UI elements optional (progressive enhancement)
- [ ] WebSocket events backward compatible (old clients ignore unknown event types)

### Performance Impact
- [ ] Agent delegation adds < 500ms overhead vs. direct LLM (for request routing and session lookup)
- [ ] SSE event processing adds < 50ms latency per event
- [ ] Database queries optimized (indexes on `conversation_id`, `agent_session_id`)
- [ ] No regression in non-agent conversations (direct LLM path unchanged)

---

## Risk Mitigation

### Primary Risks

**Risk 1: SSE Stream Reliability Over Network**
- **Issue:** Network interruptions, load balancers, or proxies may not support SSE or may terminate streams prematurely.
- **Mitigation:**
  - Implement SSE reconnection logic with `Last-Event-ID` header
  - Add stream keepalive (heartbeat events every 15 seconds)
  - Test behind common proxies (nginx, AWS ALB) and adjust timeouts
  - Fallback: poll-based status endpoint if SSE fails repeatedly
  - Document infrastructure requirements (proxy settings, timeouts)

**Risk 2: Agent Service Unavailability**
- **Issue:** Agent Service downtime causes conversation failures and poor user experience.
- **Mitigation:**
  - Circuit breaker prevents cascading failures (fall back to direct LLM)
  - Health check endpoint monitored (alert on failures)
  - Retry logic with exponential backoff (3 attempts)
  - User-facing message: "Advanced features temporarily unavailable, using standard chat"
  - Queue agent requests for later processing (optional enhancement)

**Risk 3: ASK_USER Timeout & Session Abandonment**
- **Issue:** User doesn't answer agent question, leaving session in limbo and consuming resources.
- **Mitigation:**
  - 5-minute timeout for user responses (configurable)
  - Automatic session cleanup job (mark stale sessions as `ABANDONED`)
  - User notification: "Agent question expired, starting fresh conversation"
  - Database index on `last_interaction_at` for efficient cleanup queries
  - Test timeout scenarios explicitly

**Risk 4: Chat History Explosion & Context Window Overflow**
- **Issue:** Long conversations exceed agent context window, causing errors or expensive LLM calls.
- **Mitigation:**
  - Token-budget windowing (max 4000 tokens for history)
  - Summary compression for very long conversations (Epic 3 enhancement)
  - Warn user when approaching context limits
  - Test with conversations of 100+ messages
  - Monitor token usage metrics (alert on >80% capacity)

**Risk 5: Session Correlation Conflicts**
- **Issue:** Multiple concurrent requests for same conversation create duplicate agent sessions.
- **Mitigation:**
  - Database unique constraint on `(conversation_id, status='ACTIVE')`
  - Optimistic locking for session creation
  - Return HTTP 409 Conflict if concurrent session creation attempted
  - Client-side request deduplication (disable submit button during processing)
  - Test with concurrent request simulation

### Rollback Plan

**If Epic Must Be Rolled Back:**

1. **Disable Agent Routing**: Set environment variable `AGENT_ROUTING_ENABLED=false` in ConversationService
2. **Remove Database Table**: Run migration downgrade to drop `conversation_agent_sessions`
3. **Remove Client Library**: Delete `AgentServiceClient` module (not imported if routing disabled)
4. **Preserve Agent Service**: Epic 1 service remains operational for future retry
5. **No Data Loss**: Conversation history unaffected (agent metadata only removed)

**Partial Rollback Scenarios:**

- **SSE Issues**: Fall back to polling-based agent status checks (degraded UX, but functional)
- **Routing Issues**: Route all messages to direct LLM (agent service idle)
- **ASK_USER Issues**: Disable ASK_USER feature (agent completes without questions or fails gracefully)

---

## Definition of Done

### Functional Completeness
- [ ] All 8 stories completed with acceptance criteria met
- [ ] User can send message → routed to agent → streamed response received
- [ ] Agent ASK_USER flow works end-to-end (question → answer → resume)
- [ ] Session correlation persists across conversation restarts
- [ ] Error scenarios handled gracefully (service down, timeout, stream failure)

### Quality Assurance
- [ ] Unit test coverage ≥ 80% for new integration components
- [ ] Integration tests cover all happy path and error scenarios
- [ ] Load test passes: 50 concurrent users, 10 minutes, no errors
- [ ] No memory leaks detected (heap profiling over 1000 requests)
- [ ] Security review passed (authentication, authorization, data validation)

### Documentation
- [ ] Integration architecture diagram published (shows ConversationService ↔ Agent Service flow)
- [ ] Sequence diagrams for key flows (message routing, ASK_USER, error handling)
- [ ] API client library documented with usage examples
- [ ] Configuration guide: environment variables, routing rules, timeouts
- [ ] Troubleshooting runbook: common errors and resolutions

### Operational Readiness
- [ ] Monitoring dashboards deployed (Grafana: latency, error rate, delegation rate)
- [ ] Alerts configured: agent service down, high error rate (>5%), high latency (p95 > 5s)
- [ ] Logging structured with correlation IDs (trace requests across services)
- [ ] Circuit breaker metrics exposed (open/closed state, failure count)
- [ ] Health check includes agent service connectivity

### Integration Verification
- [ ] ConversationService API unchanged (backward compatibility verified)
- [ ] Chat UI functional without code changes (graceful degradation tested)
- [ ] Non-agent conversations unaffected (performance baseline maintained)
- [ ] Database migrations reversible (upgrade + downgrade tested)

### Performance Validation
- [ ] First response chunk: < 2 seconds (p95)
- [ ] Agent routing overhead: < 500ms (session lookup + client call)
- [ ] SSE event processing: < 50ms per event (p95)
- [ ] Concurrent load: 50 users with 30% agent delegation, no errors
- [ ] Memory stable (no leaks over 1-hour test with 10,000 requests)

---

## Dependencies

### Technical Dependencies
- **Agent Service (Epic 1)**: Must be deployed and operational
- ConversationService database (PostgreSQL or equivalent)
- Python `httpx` or `aiohttp` for async HTTP/SSE client
- WebSocket infrastructure for real-time UI updates
- Monitoring stack (Prometheus, Grafana) for metrics

### External Dependencies
- Agent Service `/api/v1/agent/execute` endpoint available
- Agent Service authentication mechanism (API keys provisioned)
- Network connectivity between ConversationService and Agent Service (service mesh or direct)

### Team Dependencies
- **Required Before Start:**
  - Agent Service deployed to dev/test environment
  - API keys generated for ConversationService
  - ConversationService codebase access
  - Test user accounts with various permission levels

---

## Validation Checklist

### Scope Validation
- [x] Epic scope clearly defined (Phase 2: Integration between services)
- [x] Stories logically sequenced (client → session → history → routing → events → error handling → testing)
- [x] Success criteria measurable and testable
- [x] Epic delivers standalone value (working integration)

### Risk Assessment
- [x] Primary risks identified with mitigation strategies
- [x] Rollback plan documented and feasible
- [x] SSE reliability concerns addressed (reconnection, keepalive, fallback)
- [x] Service availability handled (circuit breaker, health checks)

### Integration Planning
- [x] ConversationService API preserved (backward compatibility)
- [x] Database schema extended (not replaced)
- [x] UI graceful degradation planned
- [x] Performance monitoring in place

---

## Story Manager Handoff

**Story Manager Handoff:**

"Please develop detailed user stories for Epic 2: ConversationService Integration & Hydration. This epic integrates two existing systems: the ConversationService (manages chat) and the Agent Service (executes ReAct agents, built in Epic 1). Key considerations:

**Existing Systems:**

*ConversationService:*
- Technology: (Specify tech stack: Node.js/Python/Java?)
- Responsibilities: Chat session management, message history storage, user authentication
- Current flows: User message → direct LLM call → response
- Database: (Specify: PostgreSQL/MongoDB/MySQL?)

*Agent Service (NEW):*
- Technology: Python 3.11, FastAPI, PostgreSQL, SSE streaming
- Responsibilities: ReAct agent execution, state persistence, tool orchestration
- API: POST `/api/v1/agent/execute` with SSE response
- Authentication: API key via `X-API-Key` header

**Integration Points:**
- ConversationService client library calls Agent Service REST API
- SSE stream consumed by ConversationService event processor
- Session IDs correlated via new database table
- Chat history extracted and injected into agent requests
- User context (user_id, org_id) propagated to agent for security filtering

**Critical Requirements:**
- Zero breaking changes to ConversationService public API
- SSE stream reliability (reconnection, keepalive, fallback to polling)
- Circuit breaker pattern for agent service unavailability (fall back to direct LLM)
- ASK_USER flow must be seamless (agent asks → user answers → execution resumes)
- Performance: first response chunk < 2 seconds, routing overhead < 500ms

**Story Sequence Rationale:**
1. Client library (Story 1) → abstraction for agent service communication
2. Session correlation (Story 2) → link conversations to agent sessions
3. History extraction (Story 3) → provide agent execution context
4. Message routing (Story 4) → decision logic for agent delegation
5. Event processing (Story 5) → real-time state updates from SSE
6. ASK_USER workflow (Story 6) → bidirectional agent-user interaction
7. Error handling (Story 7) → resilience across service boundary
8. Integration testing (Story 8) → validate end-to-end flows

Each story MUST include:
- Unit tests for new components (≥80% coverage)
- Integration tests where applicable (happy path + error scenarios)
- Performance acceptance criteria (latency, throughput)
- Backward compatibility verification (existing APIs unchanged)
- Documentation (sequence diagrams, configuration guides)
- Monitoring instrumentation (metrics, logs, traces)

The epic must enable seamless agent delegation while maintaining full backward compatibility and graceful degradation if agent service unavailable."

---

## Notes for Implementation Team

### Development Sequence Recommendation

**Week 1: Foundation (Stories 1-2)**
- Build client library with SSE support
- Test SSE consumption with mock streams
- Design session correlation schema
- Implement bidirectional lookups

**Week 2: Context & Routing (Stories 3-4)**
- Implement history extraction with windowing
- Build message router with intent detection
- Test routing logic with various message types

**Week 3: Event Processing (Story 5)**
- Build event processor for all SSE event types
- Implement async event handling with queues
- Test with simulated agent execution streams

**Week 4: Interaction & Errors (Stories 6-7)**
- Implement ASK_USER workflow end-to-end
- Build comprehensive error handling
- Test timeout scenarios and circuit breaker

**Week 5: Testing & Validation (Story 8)**
- Run integration test suite (all flows)
- Execute load tests (50 users, 10 minutes)
- Set up monitoring dashboards and alerts
- Performance tuning based on test results

### Key Design Decisions

**Why Client Library Over Direct HTTP Calls?**
- Encapsulation: abstracts SSE complexity, retry logic, authentication
- Reusability: same client usable in multiple ConversationService modules
- Testability: easy to mock for unit tests
- Maintainability: API changes isolated to client library

**Why Circuit Breaker Over Simple Retry?**
- Prevents cascading failures (avalanche effect)
- Faster failure detection (fail fast after threshold)
- Automatic recovery (half-open state testing)
- Protects agent service from overload

**Why Token-Budget Windowing Over Fixed Message Count?**
- LLM costs based on tokens, not messages
- Prevents context window overflow
- Maximizes context utility (more short messages vs. fewer long ones)
- Predictable LLM API costs

**Why Separate Event Processor Over Inline Handling?**
- Separation of concerns (SSE consumption vs. business logic)
- Async processing (non-blocking, buffered)
- Testability (inject mock events)
- Extensibility (easy to add new event types)

### Testing Strategy

**Unit Tests (pytest or equivalent):**
- Client library: mock HTTP/SSE responses
- History extractor: various conversation lengths
- Message router: routing decision logic
- Event processor: each event type handler

**Integration Tests:**
- Client library → real agent service (dev environment)
- Full flow: ConversationService → Agent Service → response
- ASK_USER: question → answer → resume
- Error scenarios: timeout, service down, invalid request

**Load Tests (Locust, k6, or JMeter):**
- 50 concurrent users, 10-minute duration
- Mix: 70% direct LLM, 30% agent delegation
- Measure: latency (p50/p95/p99), error rate, throughput
- Validate: no errors, memory stable, circuit breaker functional

**Chaos Tests (optional but recommended):**
- Kill agent service mid-execution (verify circuit breaker)
- Introduce network latency (verify timeouts and retries)
- Corrupt SSE stream (verify error handling and recovery)

---

## Success Metrics

**Integration Metrics:**
- Agent delegation rate: configurable target (e.g., 20% of conversations)
- Successful execution rate: ≥ 95% (excluding user-caused errors)
- ASK_USER completion rate: ≥ 80% (users answer within timeout)

**Performance Metrics:**
- Routing decision latency: < 100ms
- First response chunk (agent): < 2 seconds (p95)
- SSE event processing: < 50ms per event (p95)
- Memory overhead: < 50MB per active agent session

**Reliability Metrics:**
- Circuit breaker activation rate: < 1% of requests
- Retry success rate: ≥ 70% (failed requests that succeed on retry)
- Stream reconnection success rate: ≥ 90%

**User Experience Metrics:**
- User abandonment rate (ASK_USER timeout): < 20%
- Error rate visible to users: < 1%
- Conversation completion rate: ≥ 90%

