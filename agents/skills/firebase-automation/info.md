---
name: firebase-automation
description: "Firebase/Firestore admin and knowledge base management for Procaffe. Use when user needs to manage Firestore collections, sync to Pinecone, or query knowledge base."
deployment: remote
license: Proprietary
allowed-tools: [Bash, Read]
---

# Firebase Automation Skill

Provides Firebase/Firestore administration and knowledge base management for Procaffe's second brain system.

## Capabilities

### 1. Firestore Administration
- List/query/get/set/delete documents
- Collection management
- Document CRUD operations with dry-run support
- JSON output formatting

### 2. Storage Management
- Upload/download files to Firebase Storage
- List bucket contents
- Generate signed URLs
- Delete files

### 3. Knowledge Base Sync
- Sync FAQs from CSV to Firestore
- Sync Firestore data to Pinecone vector database
- Support for multiple namespaces (facebook, products, faqs)
- Incremental sync with progress tracking

### 4. Semantic Search & RAG
- Query knowledge base with natural language
- Semantic search across namespaces
- RAG-powered Q&A using Gemini
- Interactive mode for conversations
- Reranking with Cohere

---

## Configuration (config.py)

```python
# Firebase Configuration
FIREBASE_SERVICE_ACCOUNT = "firebase_service_account.json"
FIREBASE_PROJECT_ID = "procaffe-d3230"
FIREBASE_STORAGE_BUCKET = "procaffe-d3230.firebasestorage.app"

# Pinecone Configuration (Second Brain)
PINECONE_INDEX_NAME = "procaffe-kb"
PINECONE_DIMENSION = 768  # Gemini text-embedding-004
PINECONE_CLOUD = "aws"
PINECONE_REGION = "us-east-1"

# Cohere Configuration (Reranking)
COHERE_RERANK_MODEL = "rerank-v4.0-pro"  # Latest model (Dec 2025)

# Firestore Collections
CRM_LEADS_COLLECTION = "leads"
```

---

## Scripts Reference

All scripts located at `~/.claude/skills/firebase-automation/scripts/`. Use `/opt/homebrew/bin/python3`

### firebase-admin.py
**Path**: `~/.claude/skills/firebase-automation/scripts/firebase-admin.py`

**Description**: CLI for Firestore and Storage operations

**Usage**:
```bash
# Firestore operations
/opt/homebrew/bin/python3 scripts/firebase-admin.py fs list-collections
/opt/homebrew/bin/python3 scripts/firebase-admin.py fs list faqs --limit 10 --json
/opt/homebrew/bin/python3 scripts/firebase-admin.py fs get faqs/faq_abc123
/opt/homebrew/bin/python3 scripts/firebase-admin.py fs set users/user1 '{"name":"Test"}' --merge
/opt/homebrew/bin/python3 scripts/firebase-admin.py fs delete users/user1 --dry-run
/opt/homebrew/bin/python3 scripts/firebase-admin.py fs query users --where "active==true" --limit 10

# Storage operations
/opt/homebrew/bin/python3 scripts/firebase-admin.py st list images/ --limit 20
/opt/homebrew/bin/python3 scripts/firebase-admin.py st upload ./logo.png images/logo.png
/opt/homebrew/bin/python3 scripts/firebase-admin.py st download images/logo.png ./logo.png
/opt/homebrew/bin/python3 scripts/firebase-admin.py st url images/logo.png --expires 3600
/opt/homebrew/bin/python3 scripts/firebase-admin.py st delete images/logo.png --dry-run
```

**Key Arguments**:
- `fs` (firestore): Firestore commands
  - `list-collections` / `lc`: List all collections
  - `list` / `ls <collection>`: List documents in collection
  - `get <path>`: Get specific document
  - `set <path> <json>`: Set/update document
  - `delete` / `rm <path>`: Delete document
  - `query` / `q <collection>`: Query with filters
- `st` (storage): Storage commands
  - `list` / `ls [prefix]`: List files
  - `upload` / `up <local> <remote>`: Upload file
  - `download` / `dl <remote> <local>`: Download file
  - `url <remote>`: Get signed URL
  - `delete` / `rm <remote>`: Delete file
- `--dry-run`: Show what would be done
- `--json`: JSON output format
- `--limit N`: Limit results
- `--where "field==value"`: Filter query (supports ==, >, <, >=, <=)
- `--merge`: Merge with existing document (for set)
- `--expires N`: URL expiration in seconds (default: 3600)

---

### faq-import-to-firestore.py
**Path**: `~/.claude/skills/firebase-automation/scripts/faq-import-to-firestore.py`

**Description**: Import FAQ entries from CSV to Firestore `faqs` collection

**Usage**:
```bash
# Import all FAQs
/opt/homebrew/bin/python3 scripts/faq-import-to-firestore.py

# Dry run to preview
/opt/homebrew/bin/python3 scripts/faq-import-to-firestore.py --dry-run

# Import first 10 only
/opt/homebrew/bin/python3 scripts/faq-import-to-firestore.py --limit 10

# Custom CSV file
/opt/homebrew/bin/python3 scripts/faq-import-to-firestore.py --file /path/to/faqs.csv
```

**Key Arguments**:
- `--dry-run`: Show what would be done without importing
- `--limit N`: Import only first N FAQs
- `--file <path>`: Custom FAQ CSV file path (default: `data/faqs-expanded.csv`)

**CSV Format**:
- Columns: `question`, `answer`, `category`
- UTF-8 encoding (handles BOM)
- Deterministic IDs generated from question hash
- Skips duplicates automatically

---

### kb-pinecone-sync.py
**Path**: `~/.claude/skills/firebase-automation/scripts/kb-pinecone-sync.py`

**Description**: Sync Firestore content to Pinecone vector database for semantic search

**Usage**:
```bash
# Sync FAQs to Pinecone
/opt/homebrew/bin/python3 scripts/kb-pinecone-sync.py --namespace faqs

# Sync products
/opt/homebrew/bin/python3 scripts/kb-pinecone-sync.py --namespace products

# Sync Facebook posts
/opt/homebrew/bin/python3 scripts/kb-pinecone-sync.py --namespace facebook

# Dry run with limit
/opt/homebrew/bin/python3 scripts/kb-pinecone-sync.py --namespace faqs --limit 10 --dry-run

# Show index stats
/opt/homebrew/bin/python3 scripts/kb-pinecone-sync.py --stats
```

**Key Arguments**:
- `--namespace <name>`: Namespace to sync (choices: facebook, tiktok, products, leads, faqs; default: facebook)
- `--limit N`: Limit documents to sync
- `--dry-run`: Show what would be done
- `--stats`: Show index statistics only

**Environment Variables**:
- `PINECONE_API_KEY`: Pinecone API key (required)
- `GEMINI_API_KEY`: Gemini API key for embeddings (required)

**Features**:
- Incremental sync with progress tracking
- Batch upserts (100 vectors per batch)
- Rate limiting for Gemini API
- 768-dim embeddings using Gemini text-embedding-004
- Multiple namespace support for logical separation

---

### kb-query.py
**Path**: `~/.claude/skills/firebase-automation/scripts/kb-query.py`

**Description**: Semantic search and RAG-powered Q&A using Pinecone + Gemini

**Usage**:
```bash
# Ask a question (RAG mode)
/opt/homebrew/bin/python3 scripts/kb-query.py "Máy espresso có bảo hành không?"

# Search only (no RAG answer)
/opt/homebrew/bin/python3 scripts/kb-query.py "Gợi ý video về latte art" --search-only

# Search specific namespace
/opt/homebrew/bin/python3 scripts/kb-query.py "Sản phẩm mới" --namespace products

# Multiple namespaces
/opt/homebrew/bin/python3 scripts/kb-query.py "Thông tin sản phẩm" -n products -n faqs

# Verbose mode (show retrieved context)
/opt/homebrew/bin/python3 scripts/kb-query.py "Máy pha cà phê" --verbose

# Interactive mode
/opt/homebrew/bin/python3 scripts/kb-query.py --interactive
```

**Key Arguments**:
- `query`: Question to ask (positional argument)
- `--namespace` / `-n <name>`: Namespace(s) to search (can repeat; default: facebook, products, faqs)
- `--search-only` / `-s`: Only show search results, no RAG answer
- `--top-k` / `-k N`: Number of results to retrieve (default: 5)
- `--verbose` / `-v`: Show retrieved context
- `--interactive` / `-i`: Interactive mode for conversations

**Interactive Mode Commands**:
- `/quit`, `/exit`, `/q`: Exit
- `/search <query>`: Search only (no RAG)
- `/stats`: Show index statistics

**Environment Variables**:
- `PINECONE_API_KEY`: Pinecone API key (required)
- `GEMINI_API_KEY`: Gemini API key (required)

---

## Common Workflows

### Initial Setup: Import FAQs and Sync to Pinecone
```bash
# 1. Import FAQs from CSV to Firestore
/opt/homebrew/bin/python3 scripts/faq-import-to-firestore.py

# 2. Sync FAQs to Pinecone
/opt/homebrew/bin/python3 scripts/kb-pinecone-sync.py --namespace faqs

# 3. Test query
/opt/homebrew/bin/python3 scripts/kb-query.py "Máy espresso có bảo hành không?" -n faqs
```

### Manage Firestore Collections
```bash
# List all collections
/opt/homebrew/bin/python3 scripts/firebase-admin.py fs list-collections

# View FAQs
/opt/homebrew/bin/python3 scripts/firebase-admin.py fs list faqs --json

# Get specific FAQ
/opt/homebrew/bin/python3 scripts/firebase-admin.py fs get faqs/faq_abc123

# Update FAQ (merge mode)
/opt/homebrew/bin/python3 scripts/firebase-admin.py fs set faqs/faq_abc123 '{"category":"products"}' --merge
```

### Interactive Knowledge Base Query
```bash
# Start interactive session
/opt/homebrew/bin/python3 scripts/kb-query.py -i

# Sample queries in interactive mode:
# - "Máy espresso có bảo hành bao lâu?"
# - "Gợi ý video về latte art"
# - "Sản phẩm nào phù hợp với quán cafe nhỏ?"
# - /stats (to check index)
# - /quit (to exit)
```

---

## Technical Details

### Firestore Collections
- `faqs`: FAQ entries with question/answer/category
- `products`: Product catalog with specs and pricing
- `fb_posts`: Facebook content for social media
- `leads`: Customer leads and interactions
- `tiktok_accounts`: TikTok account tracking

### Pinecone Namespaces
- `facebook`: Facebook posts and content
- `products`: Product catalog
- `faqs`: Frequently asked questions
- `tiktok`: TikTok content (future)
- `leads`: Lead information (future)

### Embedding Configuration
- Model: `text-embedding-004` (Gemini)
- Dimension: 768
- Task types:
  - Document: `retrieval_document`
  - Query: `retrieval_query`

### RAG Configuration
- Generation model: `gemini-3-flash-preview`
- Context limit: 5 documents
- Min similarity score: 0.5
- Language: Vietnamese (vi)
- Reranking: Cohere `rerank-v4.0-pro`

---

## Environment Variables

```bash
# Firebase
# Uses firebase_service_account.json file

# Pinecone
PINECONE_API_KEY=your-pinecone-api-key

# Gemini
GEMINI_API_KEY=your-gemini-api-key

# Cohere (for reranking)
COHERE_API_KEY=your-cohere-api-key
```

Or add to `.env` file in project root.

---

## Error Handling

All scripts include:
- Service account validation
- API key validation
- Dry-run mode for safe testing
- Progress tracking for long operations
- Graceful error messages
- Rate limiting for API calls

---

## References

See `references/` directory for detailed documentation.
