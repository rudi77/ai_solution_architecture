# Epic 1: Agent Service Foundation & Core Infrastructure

## Epic Goal

Transform the TaskForce agent framework from a local file-based system into a containerized, stateless microservice with PostgreSQL-backed state persistence and real-time SSE streaming capabilities, establishing the foundation for Agent-as-a-Service architecture.

## Epic Description

### Existing System Context

**Current System:**
- Local agent framework (`capstone/agent_v2`) running as standalone Python application
- File-based state persistence (`StateManager`, `TodoListManager` using JSON files)
- Synchronous execution model with direct tool invocation
- RAG capabilities via Azure AI Search integration
- Technology Stack: Python 3.11, uv package manager, OpenAI GPT-4

**Integration Points:**
- Azure OpenAI API for LLM completions
- Azure AI Search for RAG functionality
- Local filesystem for state/todolist persistence
- Direct tool execution (Python, File, Shell, Git, Web)

### Enhancement Details

**What's Being Added/Changed:**

This epic delivers the **MVP foundation** for the TaskForce Agent Service by:

1. **Containerization**: Package the agent as a FastAPI microservice with Docker
2. **Database Migration**: Replace file-based persistence with PostgreSQL (tables: `agent_sessions`, `agent_state_snapshots`)
3. **API Layer**: Create REST API with SSE streaming for real-time agent execution feedback
4. **State Adapters**: Implement `DbStateManager` and `DbTodoListManager` as drop-in replacements
5. **Profile System**: Enable configuration-driven agent instantiation via `agent_profiles.yaml`

**How It Integrates:**

- **API Gateway Pattern**: FastAPI service exposes `/api/v1/agent/execute` endpoint
- **Adapter Pattern**: Database managers implement same interface as file-based managers
- **Event Streaming**: SSE protocol replaces synchronous response for real-time feedback
- **Factory Pattern**: `AgentFactory` loads profiles and injects DB-backed managers

**Success Criteria:**

- [ ] Service handles agent execution requests via REST API
- [ ] Agent state persists to PostgreSQL and survives container restarts
- [ ] SSE stream delivers real-time events (`THOUGHT`, `TOOL_START`, `TOOL_END`, `ANSWER_CHUNK`, `COMPLETE`)
- [ ] RAG tools (SemanticSearch, GetDocument) function correctly in containerized environment
- [ ] Service can hydrate existing sessions from database
- [ ] End-to-end execution: API request → Agent ReAct loop → Streamed response

---

## Stories

### Story 1: FastAPI Service Skeleton & Docker Setup
Create the containerized FastAPI application structure with health checks, configuration management, and deployment artifacts.

**Key Deliverables:**
- FastAPI app with `/health`, `/readiness` endpoints
- Dockerfile with multi-stage build
- `docker-compose.yml` with service + PostgreSQL
- Environment configuration management (`.env`, config classes)
- OpenAPI documentation at `/docs`

### Story 2: PostgreSQL Schema & Database Layer
Design and implement the database schema for agent state persistence with SQLAlchemy ORM and migration support.

**Key Deliverables:**
- Database schema: `agent_sessions`, `agent_state_snapshots` tables
- Alembic migration setup
- Database connection pooling and session management
- JSONB support for flexible state serialization
- Optimistic locking via `version` column

### Story 3: DbStateManager Implementation
Port the file-based `StateManager` to a database-backed implementation maintaining interface compatibility.

**Key Deliverables:**
- `DbStateManager` class with same API as `StateManager`
- CRUD operations for session state (answers, pending_question, todolist_id)
- JSONB serialization/deserialization for `memory_data`
- Unit tests with in-memory PostgreSQL (pytest-postgresql)
- Migration guide for existing state files

### Story 4: DbTodoListManager Implementation
Replace file-based TodoList persistence with PostgreSQL storage while preserving TodoList behavior.

**Key Deliverables:**
- `DbTodoListManager` class replacing file-based version
- TodoItem CRUD operations with JSONB storage
- TaskStatus enum persistence (PENDING, IN_PROGRESS, COMPLETED, FAILED, SKIPPED)
- Dependency graph reconstruction from database
- Unit tests for plan creation, updates, and retrieval

### Story 5: SSE Streaming Endpoint Implementation
Create the `/api/v1/agent/execute` endpoint with Server-Sent Events streaming for real-time agent execution feedback.

**Key Deliverables:**
- POST `/api/v1/agent/execute` endpoint
- SSE event stream implementation (FastAPI `StreamingResponse`)
- Event types: `THOUGHT`, `TOOL_START`, `TOOL_END`, `ANSWER_CHUNK`, `ASK_USER`, `COMPLETE`, `ERROR`
- Request validation (Pydantic models for `ExecuteRequest`)
- Error handling and graceful stream termination
- Integration tests with SSE client

### Story 6: Agent Profile System & Factory
Implement configuration-driven agent instantiation using YAML profiles and runtime context injection.

**Key Deliverables:**
- `agent_profiles.yaml` schema definition
- `AgentFactory.create()` method with profile loading
- Profile structure: `name`, `system_prompt_ref`, `model`, `tools`, `mcp_servers`
- Runtime context injection (`user_context`, `session_id`)
- Profile validation and error reporting
- Initial profiles: `rag_specialist`, `dev_ops`

### Story 7: Agent Hydration Logic & Execution Loop
Implement the core execution flow: load state from DB → inject chat history → execute ReAct loop → stream events → persist state.

**Key Deliverables:**
- Session hydration from `agent_state_snapshots`
- Chat history injection into `MessageHistory`
- Async execution loop with event generation
- Auto-save state after each ReAct step
- Session locking to prevent concurrent modifications
- Integration test: full request → execution → response cycle

### Story 8: RAG Tools Integration in Containerized Environment
Ensure Azure AI Search-based RAG tools (SemanticSearch, GetDocument) work correctly with user context filtering.

**Key Deliverables:**
- Azure AI Search connection from containerized service
- User context (`user_id`, `org_id`) propagation to RAG tools
- Security filter application in search queries
- Environment-based configuration (search endpoint, index name)
- End-to-end RAG test: question → search → retrieve → answer
- Performance baseline (latency, throughput)

---

## Compatibility Requirements

### API Compatibility
- [ ] Existing agent core logic (`agent.py`, ReAct loop) remains unchanged in behavior
- [ ] Tool interface (`Tool.execute()`) unchanged; tools work with new managers
- [ ] MessageHistory interface preserved for backward compatibility

### Database Compatibility
- [ ] Schema supports future versioning (JSONB flexibility)
- [ ] State snapshots include schema version for migration support
- [ ] Alembic migrations allow zero-downtime upgrades

### Configuration Compatibility
- [ ] Existing prompts (`prompts/rag_system_prompt.py`) reusable without changes
- [ ] Tool configurations portable between local and service environments
- [ ] Environment variables follow 12-factor app principles

### Performance Impact
- [ ] Agent execution latency: < 200ms overhead vs. local execution
- [ ] Database queries optimized (indexes on `session_id`, `updated_at`)
- [ ] Connection pooling prevents resource exhaustion
- [ ] SSE streaming starts within 100ms of request receipt

---

## Risk Mitigation

### Primary Risks

**Risk 1: State Serialization Complexity**
- **Issue:** TodoList and Memory structures are complex Python objects; JSONB serialization may lose type information or fail on custom objects.
- **Mitigation:**
  - Implement custom JSON encoders/decoders for agent-specific types
  - Use JSON Schema validation on deserialization
  - Write comprehensive serialization unit tests
  - Maintain backward compatibility via versioned schemas

**Risk 2: Concurrency & Race Conditions**
- **Issue:** Multiple requests for same `session_id` could corrupt state if not properly locked.
- **Mitigation:**
  - Implement optimistic locking with `version` column
  - Use PostgreSQL row-level locking (`SELECT ... FOR UPDATE`)
  - Return HTTP 409 Conflict for concurrent modification attempts
  - Test with concurrent request simulation

**Risk 3: SSE Stream Interruption**
- **Issue:** Network issues or client disconnects could leave agent in inconsistent state.
- **Mitigation:**
  - Persist state after EVERY step, not just at end
  - Implement idempotent resume capability
  - Add heartbeat events every 15s to detect dead connections
  - Graceful cleanup on stream abort

**Risk 4: Database Performance Bottleneck**
- **Issue:** JSONB queries on large state snapshots could slow down the service.
- **Mitigation:**
  - Index `session_id`, `updated_at`, `profile_name`
  - Implement state snapshot size limits (warn at >1MB)
  - Add database query performance monitoring
  - Plan for read replicas if needed

**Risk 5: Azure AI Search Connectivity in Container**
- **Issue:** Network policies or authentication issues in containerized environment.
- **Mitigation:**
  - Test Azure SDK credential chain (Managed Identity, env vars)
  - Implement connection retry with exponential backoff
  - Add health check for Azure AI Search connectivity
  - Provide clear error messages for auth failures

### Rollback Plan

**If Epic Must Be Rolled Back:**

1. **Keep Local Agent Operational**: Do NOT remove file-based managers until Epic 2 integration is verified
2. **Database Rollback**: Run Alembic downgrade to remove tables
3. **Container Cleanup**: `docker-compose down -v` removes service and volumes
4. **Code Rollback**: Use git tags `pre-epic-1` to restore codebase
5. **No Data Loss**: State files remain untouched during development

**Partial Rollback Scenarios:**

- **Stories 1-4 Done, SSE Fails**: Service can still use synchronous endpoints as fallback
- **Database Issues**: Temporarily re-enable file-based managers while debugging
- **Profile System Issues**: Hard-code agent creation as interim solution

---

## Definition of Done

### Functional Completeness
- [ ] All 8 stories completed with acceptance criteria met
- [ ] Service successfully handles agent execution request end-to-end
- [ ] State persists to PostgreSQL and survives container restarts
- [ ] SSE streaming delivers all event types correctly
- [ ] RAG tools execute successfully with user context filtering

### Quality Assurance
- [ ] Unit test coverage ≥ 80% for new database layer
- [ ] Integration tests cover: API → Agent → DB → SSE flow
- [ ] Load test: Service handles 10 concurrent sessions without degradation
- [ ] No memory leaks during 1-hour stress test
- [ ] Security scan passes (no critical vulnerabilities in dependencies)

### Documentation
- [ ] API documentation complete in OpenAPI/Swagger
- [ ] Database schema documented with ER diagrams
- [ ] Docker deployment guide written
- [ ] Profile configuration guide with examples
- [ ] Troubleshooting runbook for common issues

### Operational Readiness
- [ ] Health check endpoint responds with DB connectivity status
- [ ] Logging structured (JSON) with correlation IDs
- [ ] Metrics exposed for Prometheus scraping (request count, latency, error rate)
- [ ] Environment variables documented with required vs. optional
- [ ] Alembic migrations tested with upgrade/downgrade cycle

### Integration Verification
- [ ] Existing agent behavior unchanged (ReAct loop, tool execution)
- [ ] No regression in local agent tests (`pytest capstone/agent_v2/tests -q`)
- [ ] RAG functionality equivalent to local execution
- [ ] Message history compression works identically

### Performance Validation
- [ ] Agent execution overhead: < 200ms vs. local
- [ ] SSE first event: < 100ms from request
- [ ] Database query latency: p95 < 50ms
- [ ] Memory usage stable (no leaks over 1000 requests)

---

## Dependencies

### Technical Dependencies
- PostgreSQL 14+ with JSONB support
- FastAPI 0.100+
- SQLAlchemy 2.0+ with async support
- Alembic for migrations
- Azure AI Search SDK
- OpenAI Python SDK
- Docker & Docker Compose

### External Dependencies
- Azure OpenAI API access (GPT-4 deployment)
- Azure AI Search instance (existing RAG index)
- Network connectivity from container to Azure services

### Team Dependencies
- **Required Before Start:**
  - PostgreSQL instance provisioned (dev/test)
  - Azure service credentials available
  - Docker environment set up on dev machines

---

## Validation Checklist

### Scope Validation
- [x] Epic scope clearly defined (Phase 1 of 3-phase roadmap)
- [x] Stories logically sequenced (infrastructure → persistence → API → integration)
- [x] Success criteria measurable and testable
- [x] Epic delivers standalone value (working microservice)

### Risk Assessment
- [x] Primary risks identified with mitigation strategies
- [x] Rollback plan documented and feasible
- [x] Concurrency issues addressed (locking, versioning)
- [x] Performance concerns planned for (monitoring, testing)

### Integration Planning
- [x] Existing agent core preserved (no breaking changes)
- [x] Tool interface unchanged (compatibility maintained)
- [x] Database schema versioned for future evolution
- [x] APIs designed for Epic 2 integration needs

---

## Story Manager Handoff

**Story Manager Handoff:**

"Please develop detailed user stories for Epic 1: Agent Service Foundation. This epic transforms an existing local Python agent framework into a containerized microservice. Key considerations:

**Existing System:**
- Technology: Python 3.11, uv package manager, Azure OpenAI, Azure AI Search
- Current architecture: File-based state (`StateManager`, `TodoListManager` in `capstone/agent_v2`)
- ReAct agent loop: Thought → Action → Observation cycle with TodoList planning
- RAG tools with user context security filtering

**Integration Points:**
- Azure OpenAI API (existing integration must work unchanged)
- Azure AI Search (RAG functionality)
- Existing tool implementations (Python, File, Git, Shell, Web)
- Current prompt system (`prompts/rag_system_prompt.py`)

**Critical Requirements:**
- Database managers MUST implement same interface as file-based managers (drop-in replacement)
- Agent core logic (`agent.py`) should require MINIMAL changes
- SSE streaming must handle interruptions gracefully
- State persistence MUST survive container restarts
- PostgreSQL JSONB serialization must preserve type fidelity

**Story Sequence Rationale:**
1. Service skeleton first (Stories 1-2) → infrastructure foundation
2. Persistence layer (Stories 3-4) → enable stateful operation
3. API surface (Stories 5-6) → expose functionality
4. Integration (Stories 7-8) → complete end-to-end flow

Each story MUST include:
- Unit tests for new components
- Integration tests where applicable
- Migration path from file-based to DB-based (where relevant)
- Verification that existing agent behavior is preserved
- Performance acceptance criteria

The epic must maintain full backward compatibility with existing agent capabilities while establishing the foundation for service-based architecture."

---

## Notes for Implementation Team

### Development Sequence Recommendation

**Week 1-2: Infrastructure (Stories 1-2)**
- Set up FastAPI service structure
- Establish PostgreSQL connection and schema
- Verify Docker deployment works locally

**Week 3-4: Persistence Layer (Stories 3-4)**
- Implement DB managers with comprehensive tests
- Validate serialization/deserialization correctness
- Test state recovery after simulated crashes

**Week 5-6: API Surface (Stories 5-6)**
- Build SSE endpoint with event streaming
- Implement profile system and factory
- Test API with mock agent execution

**Week 7-8: Integration (Stories 7-8)**
- Wire up full execution flow
- Integrate RAG tools in container
- End-to-end testing and performance validation

### Key Design Decisions

**Why PostgreSQL over NoSQL?**
- ACID guarantees critical for state consistency
- JSONB provides schema flexibility without losing relational benefits
- Strong tooling ecosystem (Alembic, SQLAlchemy)

**Why SSE over WebSockets?**
- Simpler protocol (unidirectional: server → client)
- Native HTTP/2 multiplexing support
- Easier to implement with FastAPI
- Auto-reconnect handled by browsers
- Sufficient for agent execution streaming (no client → server needed mid-execution)

**Why Adapter Pattern for Managers?**
- Preserves existing agent code (minimal changes)
- Enables gradual migration (file-based can coexist temporarily)
- Testability: easy to mock for unit tests
- Future flexibility: could add Redis, MongoDB adapters

### Testing Strategy

**Unit Tests (pytest):**
- Database layer: CRUD operations, serialization, locking
- Factory: profile loading, validation
- Event generation: correct event types and payloads

**Integration Tests:**
- API endpoint: request → DB → SSE stream
- Agent execution: full ReAct loop with DB persistence
- RAG tools: Azure AI Search queries from container

**Load Tests (locust or similar):**
- 10 concurrent sessions, 5-minute duration
- Measure: latency p50/p95/p99, error rate, memory usage
- Validate: no memory leaks, DB connection pool stable

**Contract Tests:**
- Verify SSE event schema matches API documentation
- Validate database schema matches ORM models
- Ensure profile schema validation catches invalid configs

---

## Success Metrics

**Deployment Metrics:**
- Service start time: < 30 seconds (cold start with migrations)
- Container image size: < 500MB
- Memory footprint (idle): < 200MB

**Runtime Metrics:**
- API latency (p95): < 500ms (full agent execution excluded)
- SSE first event: < 100ms
- Database query latency (p95): < 50ms
- Concurrent session capacity: ≥ 10 without degradation

**Quality Metrics:**
- Test coverage: ≥ 80%
- Zero critical security vulnerabilities
- API documentation completeness: 100% (all endpoints documented)

**Behavioral Metrics:**
- Agent execution correctness: 100% (same results as local execution)
- State recovery success rate: 100% (after container restart)
- RAG query success rate: ≥ 99% (excluding Azure service outages)

