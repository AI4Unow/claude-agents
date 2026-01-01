# agents/tests/e2e/media/test_document_analysis.py
"""E2E tests for document upload and analysis."""
import pytest
from ..conftest import upload_file


class TestDocumentAnalysis:
    """Tests for document processing capabilities."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    @pytest.mark.media
    async def test_pdf_upload(self, telegram_client, bot_username, fixtures_dir):
        """PDF upload triggers analysis."""
        pdf_path = fixtures_dir / "sample-document.pdf"
        if not pdf_path.exists():
            pytest.skip("Sample PDF fixture not available")

        response = await upload_file(
            telegram_client,
            bot_username,
            pdf_path,
            caption="Summarize this PDF",
            timeout=60
        )

        assert response is not None, "No response to PDF upload"
        text_lower = (response.text or "").lower()

        # Should acknowledge PDF or queue
        pdf_words = ["pdf", "document", "page", "content", "queue", "analyze"]
        assert any(word in text_lower for word in pdf_words), \
            f"PDF not acknowledged: {response.text[:200] if response.text else 'no text'}"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    @pytest.mark.media
    async def test_docx_upload(self, telegram_client, bot_username, fixtures_dir):
        """DOCX upload triggers analysis."""
        docx_path = fixtures_dir / "sample-word.docx"
        if not docx_path.exists():
            pytest.skip("Sample DOCX fixture not available")

        response = await upload_file(
            telegram_client,
            bot_username,
            docx_path,
            caption="What is this document about?",
            timeout=60
        )

        assert response is not None, "No response to DOCX upload"
        assert len(response.text or "") > 10, "DOCX response too short"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    @pytest.mark.media
    async def test_xlsx_upload(self, telegram_client, bot_username, fixtures_dir):
        """XLSX upload triggers data analysis."""
        xlsx_path = fixtures_dir / "sample-spreadsheet.xlsx"
        if not xlsx_path.exists():
            pytest.skip("Sample XLSX fixture not available")

        response = await upload_file(
            telegram_client,
            bot_username,
            xlsx_path,
            caption="Analyze this spreadsheet data",
            timeout=60
        )

        assert response is not None, "No response to XLSX upload"
        text_lower = (response.text or "").lower()

        # Should reference data/spreadsheet
        data_words = ["data", "spreadsheet", "row", "column", "excel", "queue"]
        assert any(word in text_lower for word in data_words), \
            f"XLSX not analyzed: {response.text[:200] if response.text else 'no text'}"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    @pytest.mark.media
    async def test_pptx_upload(self, telegram_client, bot_username, fixtures_dir):
        """PPTX upload triggers slide summarization."""
        pptx_path = fixtures_dir / "sample-presentation.pptx"
        if not pptx_path.exists():
            pytest.skip("Sample PPTX fixture not available")

        response = await upload_file(
            telegram_client,
            bot_username,
            pptx_path,
            caption="Summarize this presentation",
            timeout=60
        )

        assert response is not None, "No response to PPTX upload"
        text_lower = (response.text or "").lower()

        # Should reference presentation/slides
        pptx_words = ["presentation", "slide", "powerpoint", "content", "queue"]
        assert any(word in text_lower for word in pptx_words), \
            f"PPTX not processed: {response.text[:200] if response.text else 'no text'}"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    @pytest.mark.media
    async def test_unsupported_file_type(self, telegram_client, bot_username, fixtures_dir):
        """Unsupported file type handled gracefully."""
        # Create a temp file with unsupported extension
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as f:
            f.write(b"test content")
            temp_path = f.name

        try:
            from pathlib import Path
            response = await upload_file(
                telegram_client,
                bot_username,
                Path(temp_path),
                caption="Process this file",
                timeout=30
            )

            # Should handle gracefully (either process or explain limitation)
            assert response is not None, "No response to unknown file"
        finally:
            import os
            os.unlink(temp_path)

    @pytest.mark.e2e
    @pytest.mark.asyncio
    @pytest.mark.media
    async def test_empty_document(self, telegram_client, bot_username, fixtures_dir):
        """Empty document handled gracefully."""
        # This test requires an empty PDF fixture
        # Skip if not available
        empty_path = fixtures_dir / "empty-document.pdf"
        if not empty_path.exists():
            pytest.skip("Empty document fixture not available")

        response = await upload_file(
            telegram_client,
            bot_username,
            empty_path,
            caption="Analyze this",
            timeout=30
        )

        # Should handle gracefully
        assert response is not None, "No response to empty document"
