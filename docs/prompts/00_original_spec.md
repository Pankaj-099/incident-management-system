# Original Engineering Assignment Spec

**Source:** Engineering Challenge document received from client.

## Challenge: Mission-Critical Incident Management System (IMS)

### Overview
Build a resilient Incident Management System designed to monitor a complex distributed stack (APIs, MCP Hosts, Distributed Caches, Async Queues, RDBMS, NoSQL stores) and manage failure mediation workflow.

### Technical Architecture Requirements

**A. Ingestion & In-Memory Processing**
- Signal Ingestion: Support high-throughput ingestion of signals
- Memory Management: Handle bursts up to 10,000 signals/sec
- Debouncing Logic: 100 signals for same Component ID within 10s → 1 Work Item

**B. Distribution & Persistence**
- Sink (Data Lake): Store high-volume raw error payloads (audit log)
- Sink (Source of Truth): Work Items and RCA records, transactional
- Cache (Hot-Path): Real-time Dashboard State
- Sink (Aggregations): Timeseries aggregations

**C. Workflow Engine**
- Alerting Strategy: Strategy Pattern for different alert types
- Work Item State: State Pattern for OPEN → INVESTIGATING → RESOLVED → CLOSED

### Functional Requirements

**Backend Engine:**
1. Async Processing
2. Mandatory RCA before CLOSED transition
3. MTTR Calculation (start_time to RCA submission)

**Incident Dashboard (UI):**
- Live Feed: Active incidents sorted by severity
- Incident Detail: Raw signals + current status
- RCA Form: start/end datetime, root cause category, fix + prevention text areas

### Technical Constraints
- Concurrency: Modern concurrency primitives
- Rate Limiting: On ingestion API
- Observability: /health endpoint + throughput metrics every 5s

### Evaluation Rubric
| Category | Weight |
|---|---|
| Concurrency & Scaling | 10% |
| Data Handling | 20% |
| LLD (Low Level Design) | 20% |
| UI/UX & Integration | 20% |
| Resilience & Testing | 10% |
| Documentation | 10% |
| Tech Stack Choices | 10% |

### Submission Requirements
1. /backend and /frontend in single repo
2. README with Architecture Diagram, Docker Compose, Backpressure explanation
3. Sample data / mock failure script
4. All prompts/spec/plans checked in
5. Bonus: creative additions
