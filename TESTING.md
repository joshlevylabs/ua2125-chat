# Testing & QA Plan - UA2-125 AI Chatbot Assistant

Comprehensive testing plan for validating the UA2-125 AI Chatbot Assistant functionality, accuracy, and reliability.

## Table of Contents

1. [Testing Overview](#testing-overview)
2. [Unit Tests](#unit-tests)
3. [Integration Tests](#integration-tests)
4. [Functional Testing](#functional-testing)
5. [Performance Testing](#performance-testing)
6. [Accuracy & Quality Testing](#accuracy--quality-testing)
7. [User Acceptance Testing](#user-acceptance-testing)
8. [Security Testing](#security-testing)
9. [Test Cases](#test-cases)

---

## Testing Overview

### Test Objectives

- Verify RAG system retrieves correct documentation
- Ensure responses are accurate and helpful
- Validate API endpoints function correctly
- Confirm UI/UX works across browsers
- Test system performance under load
- Verify security measures are effective

### Testing Environment

- **Development:** Local machine with test API key
- **Staging:** Cloud instance mirroring production
- **Production:** Live environment with monitoring

---

## Unit Tests

### Backend Components

**File: `test_embeddings_index.py`**

```python
import unittest
import numpy as np
from embeddings_index import EmbeddingsIndex

class TestEmbeddingsIndex(unittest.TestCase):
    def setUp(self):
        self.index = EmbeddingsIndex()

    def test_create_embedding(self):
        """Test single embedding generation"""
        text = "Test amplifier specification"
        embedding = self.index.create_embedding(text)

        self.assertEqual(len(embedding), 3072)  # text-embedding-3-large dimension
        self.assertIsInstance(embedding, np.ndarray)

    def test_cosine_similarity(self):
        """Test cosine similarity calculation"""
        vec_a = np.array([1.0, 0.0, 0.0])
        vec_b = np.array([1.0, 0.0, 0.0])

        similarity = self.index.cosine_similarity(vec_a, vec_b)
        self.assertAlmostEqual(similarity, 1.0)

    def test_add_documents(self):
        """Test document addition"""
        chunks = [
            {
                'content': 'Test content',
                'metadata': {'category': 'test'},
                'source': 'test.txt',
                'chunk_id': 'test-123'
            }
        ]

        success = self.index.add_documents(chunks)
        self.assertTrue(success)
        self.assertEqual(len(self.index.metadata), 1)

if __name__ == '__main__':
    unittest.main()
```

**File: `test_document_processor.py`**

```python
import unittest
from ingest_docs import DocumentProcessor

class TestDocumentProcessor(unittest.TestCase):
    def setUp(self):
        self.processor = DocumentProcessor()

    def test_chunk_text(self):
        """Test text chunking"""
        text = "A" * 2000  # Long text
        chunks = self.processor.chunk_text(text, chunk_size=800, overlap=200)

        self.assertGreater(len(chunks), 1)
        self.assertLessEqual(len(chunks[0]), 800 + 200)  # Allow overlap

    def test_chunk_text_short(self):
        """Test short text doesn't get chunked"""
        text = "Short text"
        chunks = self.processor.chunk_text(text, chunk_size=800)

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0], text)

if __name__ == '__main__':
    unittest.main()
```

---

## Integration Tests

### API Endpoint Tests

**File: `test_api.py`**

```python
import unittest
from fastapi.testclient import TestClient
from app import app

class TestAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_endpoint(self):
        """Test health check endpoint"""
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)
        self.assertIn("version", data)

    def test_chat_endpoint(self):
        """Test chat endpoint"""
        request_data = {
            "message": "What is the power output?",
            "conversation_history": []
        }

        response = self.client.post("/api/chat", json=request_data)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("response", data)
        self.assertIn("sources", data)

    def test_chat_empty_message(self):
        """Test chat with empty message"""
        request_data = {
            "message": "",
            "conversation_history": []
        }

        response = self.client.post("/api/chat", json=request_data)

        self.assertEqual(response.status_code, 422)  # Validation error

    def test_stats_endpoint(self):
        """Test stats endpoint"""
        response = self.client.get("/api/stats")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("is_loaded", data)

if __name__ == '__main__':
    unittest.main()
```

### Running Tests

```bash
cd backend

# Run all tests
python -m pytest

# Run specific test file
python -m pytest test_api.py -v

# Run with coverage
python -m pytest --cov=. --cov-report=html
```

---

## Functional Testing

### Manual Test Checklist

#### 1. Document Ingestion
- [ ] Run `ingest_docs.py` successfully
- [ ] Verify embeddings are created
- [ ] Check index files exist in `data/index/`
- [ ] Validate metadata.json structure
- [ ] Confirm chunk count matches expectations

#### 2. Server Startup
- [ ] Server starts without errors
- [ ] Port 8000 is accessible
- [ ] Health endpoint returns "healthy"
- [ ] Frontend loads at root URL

#### 3. Chat Functionality
- [ ] Welcome message displays
- [ ] User can type and send messages
- [ ] Responses are generated
- [ ] Sources are displayed
- [ ] Conversation history maintains context

#### 4. UI/UX
- [ ] Chat interface is responsive
- [ ] Styling displays correctly
- [ ] Send button works
- [ ] Enter key sends message
- [ ] Shift+Enter creates new line
- [ ] Status indicator updates correctly

#### 5. Error Handling
- [ ] Graceful handling of API errors
- [ ] User-friendly error messages
- [ ] Recovery from temporary failures
- [ ] Logging captures errors

---

## Performance Testing

### Load Testing

**Tool: Locust**

Create `locustfile.py`:

```python
from locust import HttpUser, task, between

class ChatbotUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def chat_message(self):
        self.client.post("/api/chat", json={
            "message": "What is the power output at 4 ohms?",
            "conversation_history": []
        })

    @task(2)
    def health_check(self):
        self.client.get("/health")
```

**Run load test:**

```bash
locust -f locustfile.py --host=http://localhost:8000
```

**Open:** http://localhost:8089

**Test scenarios:**
- 10 users, 5 second ramp-up
- 50 users, 10 second ramp-up
- 100 users, 30 second ramp-up

**Metrics to monitor:**
- Response time (target: <2s for chat)
- Requests per second
- Error rate (target: <1%)
- CPU/memory usage

### Stress Testing

Test system limits:
- Gradually increase users until failure
- Identify breaking point
- Verify graceful degradation

---

## Accuracy & Quality Testing

### Response Quality Test Cases

| Test Query | Expected Response Elements | Pass/Fail |
|------------|---------------------------|-----------|
| "What is the power output at 4 ohms?" | Should mention 125W per channel stereo or 250W mono | |
| "How do I connect HDMI ARC?" | Should provide step-by-step instructions | |
| "Why is my amp in protection mode?" | Should list troubleshooting steps | |
| "What's the frequency response?" | Should state 20 Hz – 20 kHz | |
| "Can it play Dolby Digital?" | Should clarify it only supports 2-channel PCM | |
| "How do I wire speakers?" | Should explain stereo and bridged modes | |
| "What accessories are available?" | Should mention mounting brackets | |

### Source Accuracy Testing

For each query, verify:
- [ ] Sources are relevant to the query
- [ ] Similarity scores are >0.7
- [ ] Content snippets match the response
- [ ] Source names are descriptive

### Hallucination Detection

Test queries **not** in knowledge base:
- "What's the UA2-125's Bluetooth range?" (no Bluetooth)
- "How do I connect to WiFi?" (no WiFi)
- "What's the warranty in Brazil?" (not specified)

**Expected behavior:** Should state information is not available in documentation.

---

## User Acceptance Testing

### UAT Test Plan

**Participants:**
- 2-3 installers/integrators
- 1-2 technical support staff
- 1 end-user representative

**Test Scenarios:**

#### Scenario 1: Installation Planning
1. User asks about physical dimensions
2. User asks about mounting options
3. User asks about power requirements

**Success criteria:** User finds information helpful for planning installation

#### Scenario 2: Troubleshooting
1. User describes protection mode issue
2. Chatbot provides troubleshooting steps
3. User follows steps

**Success criteria:** Issue is resolved or user knows next steps

#### Scenario 3: Specification Lookup
1. User asks multiple spec questions
2. Chatbot provides accurate answers
3. User compares with datasheet

**Success criteria:** Answers match official documentation

#### Scenario 4: Setup Assistance
1. User asks about HDMI ARC setup
2. Chatbot provides step-by-step guide
3. User follows guide

**Success criteria:** User successfully configures HDMI ARC

### UAT Feedback Form

```
User: _______________
Role: _______________
Date: _______________

Questions:
1. Was the chatbot easy to use? (1-5)
2. Were responses accurate? (1-5)
3. Were responses helpful? (1-5)
4. Response time acceptable? (1-5)
5. Would you use this tool? (Yes/No)

Positive feedback:
_________________________________

Issues encountered:
_________________________________

Suggestions for improvement:
_________________________________
```

---

## Security Testing

### Security Test Checklist

#### 1. Input Validation
- [ ] Test SQL injection attempts in chat input
- [ ] Test XSS payloads in chat input
- [ ] Test extremely long messages (>10,000 chars)
- [ ] Test special characters and Unicode

#### 2. API Security
- [ ] Verify CORS restrictions
- [ ] Test rate limiting (if implemented)
- [ ] Verify API key is not exposed in responses
- [ ] Test unauthorized access attempts

#### 3. Environment Security
- [ ] Verify `.env` file is not in version control
- [ ] Check logs don't contain API keys
- [ ] Verify HTTPS in production
- [ ] Test with security scanner (OWASP ZAP)

#### 4. Dependency Security

```bash
# Check for vulnerable dependencies
pip install safety
safety check

# Or use pip-audit
pip install pip-audit
pip-audit
```

---

## Test Cases

### Critical Path Test Cases

#### TC-001: Basic Chat Flow
**Preconditions:** Server running, index loaded
**Steps:**
1. Navigate to http://localhost:8000
2. Enter message: "What is the UA2-125?"
3. Click Send

**Expected:** Response with product overview, sources displayed

---

#### TC-002: HDMI ARC Setup
**Preconditions:** Server running, index loaded
**Steps:**
1. Enter: "How do I connect a TV using HDMI ARC?"
2. Send message

**Expected:** Step-by-step instructions, mentions PCM audio setting

---

#### TC-003: Specification Query
**Preconditions:** Server running, index loaded
**Steps:**
1. Enter: "What's the power output at 4 ohms?"
2. Send message

**Expected:** States 125W per channel stereo or 250W mono

---

#### TC-004: Troubleshooting Query
**Preconditions:** Server running, index loaded
**Steps:**
1. Enter: "Why is my amplifier in protection mode?"
2. Send message

**Expected:** Lists troubleshooting steps (thermal, short circuit, etc.)

---

#### TC-005: Out-of-Scope Query
**Preconditions:** Server running, index loaded
**Steps:**
1. Enter: "What's the weather today?"
2. Send message

**Expected:** Politely states this is outside scope, offers help with UA2-125

---

#### TC-006: Conversation Context
**Preconditions:** Server running, index loaded
**Steps:**
1. Enter: "What inputs does the UA2-125 have?"
2. Wait for response
3. Enter: "Which one has priority?"

**Expected:** Second response should reference input priority without needing to repeat "UA2-125"

---

#### TC-007: Empty/Invalid Input
**Preconditions:** Server running, index loaded
**Steps:**
1. Leave message field empty
2. Click Send

**Expected:** Send button disabled or validation message

---

#### TC-008: Server Restart
**Preconditions:** Server running
**Steps:**
1. Stop server
2. Restart server
3. Check health endpoint

**Expected:** Index loads successfully, status is "healthy"

---

## Regression Testing

After any code changes, run:

1. **Unit tests:** All unit tests pass
2. **API tests:** All endpoints function correctly
3. **Critical path:** All critical test cases pass
4. **Accuracy:** Sample queries return correct answers

---

## Automated Testing (CI/CD)

### GitHub Actions Workflow

Create `.github/workflows/test.yml`:

```yaml
name: Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        cd backend
        pip install -r requirements.txt
        pip install pytest pytest-cov

    - name: Run tests
      env:
        OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
      run: |
        cd backend
        pytest --cov=. --cov-report=xml

    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

---

## Bug Tracking

### Bug Report Template

```
**Title:** Brief description

**Severity:** Critical / High / Medium / Low

**Environment:**
- OS:
- Browser:
- Python version:

**Steps to Reproduce:**
1.
2.
3.

**Expected Behavior:**


**Actual Behavior:**


**Screenshots/Logs:**


**Additional Context:**

```

---

## Testing Schedule

### Pre-Launch
- Week 1: Unit tests, integration tests
- Week 2: Functional testing, UAT
- Week 3: Performance testing, security testing
- Week 4: Regression, final validation

### Post-Launch
- Daily: Automated tests in CI/CD
- Weekly: Review chatbot logs for issues
- Monthly: Full regression testing
- Quarterly: Comprehensive UAT with users

---

## Success Metrics

- **Accuracy:** >95% of responses rated accurate by UAT users
- **Response Time:** <2 seconds for chat responses
- **Uptime:** >99.5% availability
- **Error Rate:** <1% of requests fail
- **User Satisfaction:** >4.0/5.0 average rating

---

## Conclusion

This testing plan ensures the UA2-125 AI Chatbot Assistant is reliable, accurate, and user-friendly. Regular testing and monitoring will maintain quality as the system evolves.

---

**Next Steps:**
1. Implement unit tests
2. Set up CI/CD pipeline
3. Conduct UAT with target users
4. Address feedback and iterate
5. Deploy to production with monitoring
