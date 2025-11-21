# Epic 3: Advanced Agent Capabilities

## Epic Goal

Enhance the TaskForce Agent Service with advanced capabilities including Model Context Protocol (MCP) server integration for extensible tool ecosystems, approval workflows for security-critical operations, and skill memory for learning from past executions, transforming the agent from a reactive executor to an adaptive, policy-aware reasoning system.

## Epic Description

### Existing System Context

**Current System (from Epics 1-2):**
- **Agent Service**: FastAPI microservice with PostgreSQL state persistence, SSE streaming, profile-based agent instantiation
- **Native Tools**: PythonTool, FileReadTool, FileWriteTool, GitTool, WebSearchTool, RAG tools (SemanticSearch, GetDocument)
- **ConversationService Integration**: Seamless chat-to-agent delegation, session hydration, ASK_USER workflows
- **Security**: User context filtering for RAG, but no tool-level approval mechanism
- **Learning**: No memory of past successes/failures beyond session state

**Integration Points:**
- Azure OpenAI API for LLM completions
- Azure AI Search for RAG
- PostgreSQL for state persistence
- ConversationService for chat integration
- Tools execute directly without policy checks

### Enhancement Details

**What's Being Added/Changed:**

This epic delivers **Phase 3 advanced capabilities** by:

1. **MCP Integration**: Connect to external MCP servers (filesystem, database, cloud APIs) via stdio/HTTP transports, enabling dynamic tool discovery and execution
2. **Approval Workflows**: Introduce policy-driven approval gates for security-critical tools (shell execution, file writes, API calls), with human-in-the-loop or automated policy checks
3. **Skill Memory**: Implement vector-based memory to store "learned lessons" from successful/failed executions, enabling agent self-improvement and context-aware decision making
4. **Profile Expansion**: Extend agent profiles with MCP server configurations, approval policies, and memory retrieval settings
5. **Advanced Observability**: Enhanced telemetry for tool execution tracing, policy decisions, and memory retrieval effectiveness

**How It Integrates:**

- **MCP Adapter Pattern**: `MCPServerConnector` manages connections to external servers, translates tool calls to MCP protocol
- **Approval Interceptor**: Middleware layer intercepts tool execution requests, evaluates policies, and enforces approval gates
- **Memory Integration**: Vector store (PostgreSQL pgvector or separate service) stores execution memories, retrieval augments agent prompts
- **Policy Engine**: Rule-based or LLM-based policy evaluation determines approval requirements per tool/context
- **Observability Stack**: OpenTelemetry tracing for distributed tool execution, Prometheus metrics for approval rates and memory hits

**Success Criteria:**

- [ ] Agent can discover and execute tools from external MCP servers (filesystem, database, cloud APIs)
- [ ] Security-critical tools (ShellTool, FileWriteTool) require approval before execution
- [ ] Approval requests surface to appropriate authority (user, admin, automated policy engine)
- [ ] Agent retrieves relevant memories from past executions to inform current decisions
- [ ] Memory storage and retrieval demonstrably improves agent performance (fewer failures, better solutions)
- [ ] Profile system supports per-agent MCP server configs, approval policies, and memory settings
- [ ] End-to-end flow: user request → agent plans → tool requires approval → approval granted → execution → memory stored

---

## Stories

### Story 1: MCP Protocol Implementation & Server Connector
Implement the Model Context Protocol (MCP) client library to connect to external servers via stdio and HTTP transports.

**Key Deliverables:**
- `MCPServerConnector` class supporting:
  - stdio transport (subprocess communication)
  - HTTP/SSE transport (remote servers)
- MCP protocol implementation:
  - Tool discovery: `tools/list` request
  - Tool execution: `tools/call` with parameters
  - Session management: `initialize`, `ping`, `shutdown`
- Connection pooling for HTTP-based servers
- Error handling: timeout, disconnection, invalid responses
- Unit tests with mock MCP server
- Integration test with reference MCP server (filesystem-server)

### Story 2: Dynamic Tool Registry & MCP Tool Loading
Extend the agent's tool registry to dynamically load tools from MCP servers at runtime based on profile configuration.

**Key Deliverables:**
- `DynamicToolRegistry` class:
  - Loads native tools (Python, File, Git, RAG)
  - Discovers MCP tools via `tools/list`
  - Merges into unified tool list for agent
- `MCPTool` wrapper class:
  - Implements `Tool` interface
  - Translates `execute()` calls to MCP protocol
  - Handles parameter schema mapping
- Profile configuration extension:
  ```yaml
  mcp_servers:
    - name: "filesystem-server"
      transport: "stdio"
      command: ["mcp-server-filesystem", "/workspace"]
    - name: "database-server"
      transport: "http"
      url: "http://mcp-db-server:8080"
  ```
- Lazy loading: connect to MCP servers on first use (not at service start)
- Health checks: periodic ping to MCP servers, remove unhealthy ones
- Unit tests: tool discovery, parameter schema mapping
- Integration test: agent executes MCP tool from external server

### Story 3: Tool Approval Metadata & Policy Schema
Define the approval policy schema and extend tool definitions with approval metadata.

**Key Deliverables:**
- Approval metadata in tool definitions:
  ```python
  class ShellTool(Tool):
      requires_approval = True
      approval_policy = "shell_execution"
      risk_level = "HIGH"
  ```
- Policy schema YAML:
  ```yaml
  policies:
    shell_execution:
      approval_type: "human"  # or "automated"
      approvers: ["admin", "security_team"]
      timeout: 300  # seconds
      auto_approve_if:
        - user_role: "admin"
        - command_matches: "^ls|pwd|echo"
    file_write:
      approval_type: "automated"
      conditions:
        - path_not_matches: "/etc|/sys|/proc"
        - file_size_under: 10485760  # 10MB
  ```
- Policy engine interface: `PolicyEngine.evaluate(tool, params, context) → ApprovalDecision`
- Database schema: `approval_requests` table
  - Fields: `request_id`, `session_id`, `tool_name`, `params`, `status` (PENDING/APPROVED/DENIED), `requested_at`, `decided_at`, `approver`, `decision_reason`
- Unit tests: policy schema validation, metadata extraction

### Story 4: Approval Gate Execution Flow
Implement the runtime approval workflow that intercepts tool execution, requests approval, and resumes execution upon decision.

**Key Deliverables:**
- `ApprovalInterceptor` middleware:
  - Wraps tool execution
  - Checks `requires_approval` flag
  - Evaluates policy: auto-approve or request human approval
- Approval request generation:
  - Creates record in `approval_requests` table
  - Emits SSE event: `APPROVAL_REQUIRED` with tool details
  - Pauses agent execution (similar to ASK_USER)
- Approval decision endpoint: POST `/api/v1/agent/approve`
  - Body: `{"request_id": "...", "decision": "approved|denied", "reason": "..."}`
  - Updates `approval_requests` status
  - Resumes agent execution if approved
- Timeout handling: auto-deny after policy timeout
- Audit logging: all approval decisions logged with approver identity
- SSE events:
  - `APPROVAL_REQUIRED`: `{"tool": "shell", "command": "rm -rf /", "risk": "HIGH"}`
  - `APPROVAL_GRANTED`: `{"tool": "shell", "approver": "admin@company.com"}`
  - `APPROVAL_DENIED`: `{"tool": "shell", "reason": "Too risky"}`
- Unit tests: approval flow, auto-approve conditions, timeout
- Integration test: tool requires approval → user approves → execution continues

### Story 5: Automated Policy Engine
Build the automated policy evaluation engine for rule-based approval decisions without human intervention.

**Key Deliverables:**
- `RuleBasedPolicyEngine` class:
  - Evaluates conditions: regex matching, value comparisons, role checks
  - Supports AND/OR logic for complex policies
  - Returns decision: `APPROVED`, `DENIED`, `REQUIRES_HUMAN`
- Condition types:
  - `user_role`: Check user's role/permissions
  - `param_matches`: Regex match on tool parameters
  - `param_not_matches`: Inverse regex match
  - `value_under/over`: Numeric comparisons
  - `time_of_day`: Time-based restrictions (e.g., no DB writes during business hours)
- LLM-based policy engine (optional enhancement):
  - Use LLM to evaluate natural language policies
  - Provide tool context and user request
  - LLM returns decision with reasoning
- Policy versioning: track policy changes, audit trail
- Policy testing framework: validate policies against test cases
- Unit tests: each condition type, complex policies (AND/OR)
- Integration test: automated approval flow end-to-end

### Story 6: Skill Memory Storage & Vector Indexing
Implement the memory storage system to persist execution memories with vector embeddings for semantic retrieval.

**Key Deliverables:**
- Memory storage options:
  - PostgreSQL with `pgvector` extension (preferred for simplicity)
  - Or Azure AI Search (reuse existing RAG infrastructure)
- Database schema: `agent_memories` table
  - Fields: `memory_id`, `agent_profile`, `mission_type`, `outcome` (SUCCESS/FAILURE), `lesson_text`, `embedding` (vector), `context`, `created_at`
- `MemoryManager` class:
  - `store_memory(lesson, context, outcome)`: stores execution memory with embedding
  - `retrieve_memories(query, top_k=5)`: semantic search for relevant memories
  - Uses OpenAI embeddings API or Azure OpenAI embeddings
- Memory extraction logic:
  - At end of agent execution (COMPLETE or ERROR)
  - LLM generates lesson: "When user asks X and tool Y fails, try Z instead"
  - Stores with context: mission goal, tools used, success/failure
- Vector indexing: pgvector index on embedding column for fast search
- Unit tests: memory CRUD, embedding generation
- Integration test: store memory → retrieve by semantic query

### Story 7: Memory Retrieval & Agent Prompt Augmentation
Integrate memory retrieval into the agent's ReAct loop to provide learned lessons as additional context.

**Key Deliverables:**
- Memory retrieval trigger points:
  - At mission start: retrieve memories relevant to mission goal
  - Before tool execution: retrieve memories about tool usage
  - After tool failure: retrieve memories about similar failures
- Prompt augmentation strategy:
  - Inject memories into system prompt: "Past lessons: ..."
  - Or inject into user message context: "Relevant experiences: ..."
  - Limit: top 3-5 memories to avoid context overflow
- Memory relevance scoring:
  - Semantic similarity (cosine distance)
  - Recency bias (recent memories weighted higher)
  - Outcome filtering (prefer successful outcomes for guidance, failures for warnings)
- Memory management:
  - Deduplication: similar memories merged
  - Expiration: old memories archived after 90 days
  - User feedback: "Was this memory helpful?" for reinforcement learning
- Agent profile configuration:
  ```yaml
  memory:
    enabled: true
    retrieval_triggers: ["mission_start", "tool_failure"]
    top_k: 3
    recency_days: 30
  ```
- Unit tests: retrieval logic, prompt augmentation, relevance scoring
- A/B test: agent with memory vs. without memory (measure success rate, efficiency)

### Story 8: Profile System Expansion & End-to-End Validation
Extend agent profiles to include MCP servers, approval policies, and memory settings, and validate all advanced capabilities end-to-end.

**Key Deliverables:**
- Extended profile schema:
  ```yaml
  profiles:
    advanced_dev_agent:
      name: "DevOps Automator with Approval"
      system_prompt_ref: "prompts.devops:SYSTEM_PROMPT"
      model: "gpt-4"
      tools:
        - "PythonTool"
        - "GitTool"
      mcp_servers:
        - name: "filesystem-server"
          transport: "stdio"
          command: ["mcp-server-filesystem", "/workspace"]
      approval_policies:
        - tool: "ShellTool"
          policy: "shell_execution"
        - tool: "FileWriteTool"
          policy: "file_write"
      memory:
        enabled: true
        retrieval_triggers: ["mission_start", "tool_failure"]
        top_k: 3
  ```
- Profile validation on load (schema validation)
- Profile hot-reload (update profiles without service restart)
- Profile versioning (track changes, rollback capability)
- End-to-end test scenarios:
  1. **MCP Integration**: Agent uses MCP filesystem tool to read/write files
  2. **Approval Workflow**: Agent attempts shell command → approval required → user approves → execution succeeds
  3. **Automated Approval**: Agent writes small file → auto-approved by policy → execution succeeds
  4. **Memory Learning**: Agent fails task → stores memory → retries similar task → retrieves memory → succeeds
  5. **Combined Flow**: Agent with MCP tools, approval gates, and memory enabled
- Load test: 20 agents with advanced features, 10-minute duration
- Performance validation:
  - MCP tool execution overhead: < 500ms
  - Approval request creation: < 100ms
  - Memory retrieval: < 200ms
  - Overall latency increase: < 1 second vs. basic agent
- Documentation:
  - MCP server integration guide
  - Approval policy authoring guide
  - Memory system architecture
  - Profile configuration reference

---

## Compatibility Requirements

### API Compatibility
- [ ] Existing agent profiles (basic, rag_specialist) work without changes
- [ ] Agents without MCP/approval/memory configs function identically to Epic 1/2
- [ ] New SSE event types (APPROVAL_REQUIRED, APPROVAL_GRANTED) optional for clients
- [ ] Backward compatibility: old clients ignore new events

### Database Compatibility
- [ ] New tables (`approval_requests`, `agent_memories`) do not conflict with existing schema
- [ ] Migrations reversible (can disable advanced features and drop tables)
- [ ] pgvector extension optional (service starts without it, memory disabled)

### Tool Compatibility
- [ ] Existing native tools work unchanged
- [ ] Tools without `requires_approval` flag execute normally (no approval checks)
- [ ] MCP tools integrate seamlessly with native tools in agent's tool list

### Performance Impact
- [ ] Agents without advanced features: no performance degradation
- [ ] MCP tool execution: < 500ms overhead vs. native tools
- [ ] Approval checks: < 100ms for policy evaluation
- [ ] Memory retrieval: < 200ms for top-5 semantic search
- [ ] Overall impact: < 1 second for agents with all advanced features enabled

---

## Risk Mitigation

### Primary Risks

**Risk 1: MCP Server Stability & Trust**
- **Issue:** External MCP servers may be unreliable, slow, or malicious (arbitrary code execution risk).
- **Mitigation:**
  - Sandboxing: run MCP servers in containers with resource limits (CPU, memory, network)
  - Timeout enforcement: 30-second max per tool call, 5-minute max per session
  - Allowlist: only connect to pre-approved MCP servers (no user-provided URLs)
  - Health monitoring: disconnect servers with >10% error rate
  - Audit logging: all MCP tool calls logged for security review
  - Test with reference MCP servers first (filesystem, fetch, postgres)

**Risk 2: Approval Workflow Abuse & Deadlocks**
- **Issue:** Approval requests pile up, no approvers available, agent sessions stuck indefinitely.
- **Mitigation:**
  - Timeout: auto-deny after policy timeout (default 5 minutes)
  - Fallback approvers: if primary approver unavailable, escalate to secondary
  - Approval queue monitoring: alert if >10 pending approvals
  - User notification: email/Slack notification for approval requests
  - Emergency bypass: admin can force-approve/deny all pending requests
  - Test with scenarios: no approvers available, approver delays response

**Risk 3: Memory Poisoning & Hallucination Amplification**
- **Issue:** Agent stores incorrect "lessons," retrieves them later, amplifies errors over time.
- **Mitigation:**
  - Human review: admin dashboard to review/edit/delete memories
  - Confidence scoring: weight memories by success rate (ignore memories from failed missions)
  - Diversity: retrieve memories from different contexts (avoid echo chamber)
  - Expiration: old memories archived after 90 days (prevent stale knowledge)
  - User feedback loop: "Was this helpful?" to reinforce good memories, suppress bad ones
  - A/B testing: validate memory improves performance before full rollout

**Risk 4: Vector Search Performance Degradation**
- **Issue:** As memory table grows (10K+ memories), retrieval latency increases.
- **Mitigation:**
  - Database indexing: pgvector index on embedding column (HNSW or IVFFlat)
  - Query optimization: limit search to recent N months (default 6 months)
  - Caching: cache top-k memories for common queries (TTL 1 hour)
  - Archiving: move old memories to cold storage (S3) after 1 year
  - Monitoring: alert if p95 latency > 500ms
  - Load test: 10K memories, 100 concurrent retrieval requests

**Risk 5: Policy Engine Complexity & Misconfiguration**
- **Issue:** Complex policies may have unintended side effects, blocking legitimate operations or allowing dangerous ones.
- **Mitigation:**
  - Policy testing framework: validate policies against test cases before deployment
  - Dry-run mode: log policy decisions without enforcing (for testing)
  - Audit trail: all policy decisions logged with reasoning
  - Policy review: security team reviews policies before production
  - Fail-safe defaults: if policy evaluation errors, default to DENY (safer)
  - LLM-based explanation: policy engine explains why decision made (for debugging)

### Rollback Plan

**If Epic Must Be Rolled Back:**

1. **Disable Advanced Features**: Set environment variables:
   - `MCP_ENABLED=false`
   - `APPROVAL_WORKFLOWS_ENABLED=false`
   - `MEMORY_ENABLED=false`
2. **Remove Database Extensions**: Drop pgvector extension (if no other dependencies)
3. **Remove Database Tables**: Run migrations downgrade to drop `approval_requests`, `agent_memories`
4. **Revert Profiles**: Remove MCP/approval/memory configs from profiles (agents fall back to basic tools)
5. **No Data Loss**: Existing sessions, conversations, and basic agent state preserved

**Partial Rollback Scenarios:**

- **MCP Issues**: Disable MCP servers per profile (agents use native tools only)
- **Approval Issues**: Set all policies to auto-approve (bypass approval gates temporarily)
- **Memory Issues**: Disable memory retrieval (agents work without learned lessons)

---

## Definition of Done

### Functional Completeness
- [ ] All 8 stories completed with acceptance criteria met
- [ ] Agent can discover and execute tools from external MCP servers
- [ ] Security-critical tools require approval before execution
- [ ] Approval requests processed (human or automated) and agent resumes execution
- [ ] Agent stores execution memories with vector embeddings
- [ ] Agent retrieves relevant memories to inform decisions
- [ ] Profile system supports MCP servers, approval policies, and memory settings

### Quality Assurance
- [ ] Unit test coverage ≥ 80% for new components (MCP, approval, memory)
- [ ] Integration tests cover all advanced feature combinations
- [ ] Security review passed: MCP sandboxing, approval audit, memory access control
- [ ] Load test: 20 agents with advanced features, 10 minutes, no errors
- [ ] A/B test: agents with memory show measurable improvement (success rate, efficiency)

### Documentation
- [ ] MCP integration guide with example servers (filesystem, database, cloud APIs)
- [ ] Approval policy authoring guide with examples (shell, file write, API calls)
- [ ] Memory system architecture document (storage, retrieval, augmentation)
- [ ] Profile configuration reference (extended schema with all options)
- [ ] Troubleshooting runbook (MCP connection issues, approval deadlocks, memory performance)

### Operational Readiness
- [ ] Monitoring dashboards: MCP tool usage, approval rates, memory hit rate
- [ ] Alerts: MCP server down, approval queue backup (>10 pending), memory latency >500ms
- [ ] Logging: structured logs with correlation IDs for distributed tracing
- [ ] Metrics: Prometheus metrics for MCP latency, approval decisions, memory retrieval time
- [ ] Admin dashboard: review approval requests, manage memories, monitor MCP servers

### Integration Verification
- [ ] Existing agents (basic, rag_specialist) work unchanged
- [ ] Agents without advanced features: no performance regression
- [ ] ConversationService handles new SSE events gracefully (APPROVAL_REQUIRED, etc.)
- [ ] Database migrations reversible (upgrade + downgrade tested)

### Performance Validation
- [ ] MCP tool execution: < 500ms overhead vs. native tools
- [ ] Approval request processing: < 100ms (policy evaluation + database insert)
- [ ] Memory retrieval: < 200ms (vector search for top-5 memories)
- [ ] Overall agent with all features: < 1 second additional latency vs. basic agent
- [ ] Memory storage: 100K+ memories supported with <500ms p95 retrieval latency

---

## Dependencies

### Technical Dependencies
- **Agent Service (Epics 1-2)**: Core infrastructure operational
- PostgreSQL with pgvector extension (or Azure AI Search for memory)
- MCP protocol specification (model-context-protocol.org)
- Reference MCP servers for testing (filesystem, fetch, postgres)
- OpenAI Embeddings API or Azure OpenAI embeddings
- OpenTelemetry for distributed tracing (optional but recommended)

### External Dependencies
- MCP servers deployed and accessible (stdio or HTTP)
- Approval notification system (email, Slack, or admin dashboard)
- Vector database operational (pgvector installed or Azure AI Search provisioned)

### Team Dependencies
- **Required Before Start:**
  - pgvector extension installed on PostgreSQL (or Azure AI Search provisioned)
  - MCP servers deployed for testing (at least filesystem-server)
  - Approval policy definitions drafted (security team input)
  - Admin dashboard or notification system available

---

## Validation Checklist

### Scope Validation
- [x] Epic scope clearly defined (Phase 3: Advanced capabilities)
- [x] Stories logically sequenced (MCP → approval → memory → integration)
- [x] Success criteria measurable and testable
- [x] Epic delivers standalone value (extensible, secure, adaptive agent)

### Risk Assessment
- [x] Primary risks identified with mitigation strategies
- [x] Rollback plan documented and feasible
- [x] MCP server trust and sandboxing addressed
- [x] Approval workflow deadlock prevention planned
- [x] Memory quality and performance concerns mitigated

### Integration Planning
- [x] Backward compatibility maintained (agents without advanced features unchanged)
- [x] New capabilities optional (enabled per profile)
- [x] Performance impact minimal for basic agents
- [x] Database schema extensible for future enhancements

---

## Story Manager Handoff

**Story Manager Handoff:**

"Please develop detailed user stories for Epic 3: Advanced Agent Capabilities. This epic extends the agent service (Epics 1-2) with three major capabilities: MCP integration, approval workflows, and skill memory. Key considerations:

**Existing System:**
- Agent Service: FastAPI microservice, PostgreSQL state, SSE streaming, profile-based agents
- Native Tools: Python, File, Git, Web, RAG (SemanticSearch, GetDocument)
- ConversationService integration: chat delegation, session hydration, ASK_USER workflows
- No tool-level security policies or learning mechanisms

**New Capabilities:**

*1. MCP Integration:*
- Connect to external tool servers via stdio/HTTP transports
- Dynamically discover and load tools from MCP servers
- Profile-based MCP server configuration
- Sandboxing and health monitoring

*2. Approval Workflows:*
- Policy-driven approval gates for security-critical tools
- Human-in-the-loop and automated policy engines
- SSE events for approval requests (APPROVAL_REQUIRED, APPROVAL_GRANTED, APPROVAL_DENIED)
- Timeout handling and audit logging

*3. Skill Memory:*
- Vector-based memory storage (PostgreSQL pgvector or Azure AI Search)
- Automatic lesson extraction from execution outcomes
- Semantic retrieval to inform future decisions
- Prompt augmentation with relevant memories

**Integration Points:**
- MCP protocol (model-context-protocol.org specification)
- PostgreSQL pgvector extension for vector search
- OpenAI Embeddings API for memory encoding
- ConversationService for approval UX (new SSE events)
- Existing tool registry and agent ReAct loop

**Critical Requirements:**
- Backward compatibility: agents without advanced features work unchanged
- Security: MCP servers sandboxed, approval audit trails, memory access control
- Performance: <1 second overhead with all features enabled
- Configurability: all features optional, enabled per profile
- Observability: metrics for MCP usage, approval rates, memory effectiveness

**Story Sequence Rationale:**
1. MCP protocol & connector (Stories 1-2) → extensible tool ecosystem foundation
2. Approval metadata & flow (Stories 3-5) → security and policy enforcement
3. Memory storage & retrieval (Stories 6-7) → learning and adaptation
4. Profile expansion & validation (Story 8) → configuration system and end-to-end testing

Each story MUST include:
- Unit tests for new components (≥80% coverage)
- Integration tests with real MCP servers / approval flows / memory retrieval
- Security validation (sandboxing, audit logging, access control)
- Performance benchmarks (latency, throughput, resource usage)
- Documentation (architecture diagrams, configuration guides, troubleshooting)
- Monitoring instrumentation (metrics, logs, traces)

The epic must deliver production-ready advanced capabilities while maintaining full backward compatibility and operational safety."

---

## Notes for Implementation Team

### Development Sequence Recommendation

**Week 1-2: MCP Foundation (Stories 1-2)**
- Implement MCP protocol client (stdio + HTTP transports)
- Build dynamic tool registry and MCP tool wrappers
- Test with filesystem-server and fetch-server
- Validate tool discovery and execution

**Week 3-4: Approval Infrastructure (Stories 3-5)**
- Define approval metadata and policy schema
- Implement approval interceptor and workflow
- Build rule-based policy engine
- Test with shell and file write tools

**Week 5-6: Memory System (Stories 6-7)**
- Set up pgvector or Azure AI Search for memory storage
- Implement memory extraction and storage
- Build retrieval and prompt augmentation logic
- A/B test memory effectiveness

**Week 7-8: Integration & Validation (Story 8)**
- Extend profile schema for all advanced features
- End-to-end testing (MCP + approval + memory combined)
- Load testing and performance optimization
- Documentation and operational readiness

### Key Design Decisions

**Why MCP Over Custom Protocol?**
- Industry standard (Anthropic, open-source community)
- Ecosystem of existing servers (filesystem, database, cloud APIs)
- Well-documented protocol with reference implementations
- Community-maintained client libraries

**Why Approval Interceptor Over Tool-Level Checks?**
- Centralized policy enforcement (single point of control)
- Easier to audit and modify policies
- Transparent to tool implementations (tools don't need approval logic)
- Consistent approval UX across all tools

**Why pgvector Over Dedicated Vector DB?**
- Simpler architecture (fewer external dependencies)
- Transactional consistency (memories stored with agent state)
- Lower operational overhead (no separate service to manage)
- Sufficient performance for expected scale (<100K memories)

**Why LLM-Generated Memories Over Manual Entry?**
- Scalability: automatic memory generation for every execution
- Consistency: structured format, no human entry errors
- Timeliness: memories captured immediately after execution
- Context-rich: includes full execution context, not just summary

### Testing Strategy

**Unit Tests (pytest):**
- MCP: protocol message encoding/decoding, transport layer
- Approval: policy evaluation, condition matching, timeout logic
- Memory: embedding generation, vector search, relevance scoring

**Integration Tests:**
- MCP: connect to real servers (filesystem, fetch), execute tools
- Approval: full workflow (request → decision → resume), automated policies
- Memory: store memory → retrieve by query, prompt augmentation

**Load Tests (Locust or k6):**
- 20 agents with advanced features, 10-minute duration
- Mix: 50% native tools, 30% MCP tools, 20% tools requiring approval
- Measure: latency (p50/p95/p99), error rate, resource usage
- Validate: no memory leaks, MCP connections stable, approval queue drains

**Security Tests:**
- MCP: malicious server attempts (infinite loops, resource exhaustion)
- Approval: policy bypass attempts, concurrent approval requests
- Memory: unauthorized access attempts, memory injection attacks

**A/B Tests:**
- Memory effectiveness: agents with vs. without memory on same tasks
- Measure: success rate, task completion time, tool usage efficiency
- Target: ≥10% improvement with memory enabled

---

## Success Metrics

**Capability Adoption:**
- MCP usage rate: ≥20% of tool calls use MCP tools (within 3 months)
- Approval enforcement: 100% of flagged tools require approval (no bypasses)
- Memory utilization: ≥50% of agent executions retrieve memories

**Operational Metrics:**
- MCP tool execution success rate: ≥95%
- Approval decision time: <2 minutes average (human), <100ms (automated)
- Memory retrieval accuracy: ≥80% (relevant memories in top-5)

**Performance Metrics:**
- MCP tool latency: <500ms overhead vs. native tools
- Approval check latency: <100ms (policy evaluation)
- Memory retrieval latency: <200ms (vector search)

**Quality Metrics:**
- Agent improvement with memory: ≥10% higher success rate vs. without memory
- Policy effectiveness: <1% false positives (legitimate operations blocked)
- MCP server stability: ≥99% uptime for approved servers

**Security Metrics:**
- Approval audit coverage: 100% of critical tool executions logged
- Policy violation rate: <0.1% (unauthorized tool executions)
- MCP sandbox escapes: 0 (all executions contained)

