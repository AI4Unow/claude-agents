---
name: gemini-vision
description: Multi-modal image and document analysis. Screenshots, diagrams, PDFs, video frames.
category: vision
deployment: both
triggers:
  - "[image attached]"
  - "analyze this image"
  - "what's in this"
  - "read this document"
---

# Gemini Vision

Advanced image and document understanding.

## Capabilities

- Image understanding + Q&A
- Screenshot → code generation
- Diagram/chart interpretation
- Document/PDF parsing
- Receipt/invoice extraction
- Handwriting recognition

## Usage

Via Telegram: Send image with caption like "Analyze this"

Via API:
```json
{
  "skill": "gemini-vision",
  "task": "Extract the text from this screenshot",
  "context": {
    "image_base64": "...",
    "media_type": "image/png"
  }
}
```

## Supported Formats

- Images: JPEG, PNG, GIF, WebP
- Documents: PDF (first pages)
- Media types: image/jpeg, image/png, application/pdf

## Examples

- "What code is in this screenshot?"
- "Explain this architecture diagram"
- "Extract text from this receipt"
- "What's wrong with this UI design?"
