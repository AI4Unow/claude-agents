# E2E Test Fixtures

Test files for media handling E2E tests.

## Files

| File | Purpose | Size | Content |
|------|---------|------|---------|
| sample-image.jpg | Vision tests | ~100KB | Nature photo |
| sample-screenshot.png | OCR tests | ~200KB | Screenshot with text |
| sample-document.pdf | PDF analysis | ~100KB | 2-page document |
| sample-spreadsheet.xlsx | Data analysis | ~50KB | Sales data |
| sample-presentation.pptx | Slide summarization | ~500KB | 5 slides |
| sample-word.docx | Document analysis | ~50KB | Article text |
| sample-voice.ogg | Transcription | ~100KB | 5-sec speech |

## Creating Fixtures

### sample-image.jpg
Use any CC0 nature image, resize to 800x600.

### sample-screenshot.png
Take screenshot of text (e.g., this README) for OCR testing.

### sample-document.pdf
Create 2-page PDF with clear headings and paragraphs.

### sample-spreadsheet.xlsx
Create simple sales data table (10 rows, 5 columns).

### sample-presentation.pptx
Create 5-slide deck with titles and bullet points.

### sample-word.docx
Create document with heading + 3 paragraphs.

### sample-voice.ogg
Record 5-second speech: "This is a test message for transcription."

## Usage

```python
@pytest.mark.media
async def test_image_upload(telegram_client, bot_username, sample_image):
    response = await upload_file(telegram_client, bot_username, sample_image)
    assert response is not None
```

## Note

Fixture files need to be created manually or downloaded. Media tests will be skipped if fixtures are not present.
