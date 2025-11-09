# 6. Success Metrics

### 6.1 Primary Metric (UX)

**Click-Through-Rate Reduction:**
Reduction in the rate at which users open source documents after receiving agent responses. Target: 70% reduction (users open source documents only 30% of the time vs. 100% baseline).

### 6.2 Secondary Metrics (Quality)

**Answer Quality Rating:**
User-rated answer quality (5-point scale). Target: Average rating ≥4.0.

**Multimodal Response Rate:**
Percentage of responses that include both text and relevant images. Target: ≥60% for queries where images exist in index.

**Citation Accuracy:**
Percentage of responses with complete and correct source citations. Target: 100%.

### 6.3 Agent Efficiency Metrics

**Plan Completion Rate:**
Rate of successfully completed TodoLists without human intervention. Target: ≥80%.

**Clarification Rate:**
How often the agent asks for user clarification. Target: <20% (indicates good query understanding).

**Tool Success Rate:**
Percentage of RAG tool executions that succeed. Target: ≥95%.

### 6.4 Performance Metrics

**Search Latency:**
Average time for semantic search to return results. Target: <2 seconds.

**End-to-End Response Time:**
Time from mission start to COMPLETE event. Target: <10 seconds for typical queries.

**Agent Overhead:**
RAG agent initialization time vs. standard agent. Target: <500ms difference.

---
