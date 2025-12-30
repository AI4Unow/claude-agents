# Firestore Indexes

Required composite indexes for complex queries in the Agents system.

## Overview

Firebase Firestore requires composite indexes for queries with multiple conditions or sorting. This document lists all required indexes for the application.

## Index Definitions

### task_queue

| Fields | Order | Purpose |
|--------|-------|---------|
| status ASC, created_at ASC | COLLECTION | Get pending tasks in order |
| user_id ASC, status ASC, created_at DESC | COLLECTION | User's tasks by status |

### reports

| Fields | Order | Purpose |
|--------|-------|---------|
| user_id ASC, createdAt DESC | COLLECTION | User's reports newest first |

### entities (II Framework)

| Fields | Order | Purpose |
|--------|-------|---------|
| type ASC, key ASC, valid_from DESC | COLLECTION | Temporal entity lookup |
| type ASC, key ASC, valid_until ASC | COLLECTION | Current entity lookup |

### reminders

| Fields | Order | Purpose |
|--------|-------|---------|
| user_id ASC, due_at ASC | COLLECTION | User's upcoming reminders |
| due_at ASC, status ASC | COLLECTION | Due reminders to process |

### tasks

| Fields | Order | Purpose |
|--------|-------|---------|
| type ASC, status ASC, priority DESC, createdAt ASC | COLLECTION | Prioritized task queue |

### faq_entries

| Fields | Order | Purpose |
|--------|-------|---------|
| enabled ASC, priority DESC | COLLECTION | Active FAQs by priority |

### user_profiles

| Fields | Order | Purpose |
|--------|-------|---------|
| tier ASC, last_active DESC | COLLECTION | Users by tier |

## Deployment

### Using Firebase CLI

1. Create `firestore.indexes.json`:

```json
{
  "indexes": [
    {
      "collectionGroup": "task_queue",
      "fields": [
        {"fieldPath": "status", "order": "ASCENDING"},
        {"fieldPath": "created_at", "order": "ASCENDING"}
      ]
    },
    {
      "collectionGroup": "task_queue",
      "fields": [
        {"fieldPath": "user_id", "order": "ASCENDING"},
        {"fieldPath": "status", "order": "ASCENDING"},
        {"fieldPath": "created_at", "order": "DESCENDING"}
      ]
    },
    {
      "collectionGroup": "reports",
      "fields": [
        {"fieldPath": "user_id", "order": "ASCENDING"},
        {"fieldPath": "createdAt", "order": "DESCENDING"}
      ]
    },
    {
      "collectionGroup": "entities",
      "fields": [
        {"fieldPath": "type", "order": "ASCENDING"},
        {"fieldPath": "key", "order": "ASCENDING"},
        {"fieldPath": "valid_from", "order": "DESCENDING"}
      ]
    },
    {
      "collectionGroup": "reminders",
      "fields": [
        {"fieldPath": "user_id", "order": "ASCENDING"},
        {"fieldPath": "due_at", "order": "ASCENDING"}
      ]
    },
    {
      "collectionGroup": "reminders",
      "fields": [
        {"fieldPath": "due_at", "order": "ASCENDING"},
        {"fieldPath": "status", "order": "ASCENDING"}
      ]
    }
  ]
}
```

2. Deploy:
```bash
firebase deploy --only firestore:indexes
```

### Manual Creation via Console

1. Go to Firebase Console → Firestore Database
2. Click "Indexes" tab
3. Click "Add Index"
4. Configure fields and order
5. Click "Create"

## Automatic Index Creation

Firestore will suggest indexes when queries fail with missing index errors. Links are provided in error messages to create missing indexes directly.

## Monitoring

Check index status:
```bash
firebase firestore:indexes
```

## Cleanup

Remove unused indexes to reduce costs:
```bash
firebase firestore:indexes:delete INDEX_ID
```
