"""Gemini client using google-genai SDK with Vertex AI."""
import os
import json
import time
import tempfile
from typing import List, Dict, Optional, Callable, Any, AsyncGenerator
from dataclasses import dataclass

from src.utils.logging import get_logger
from src.core.resilience import gemini_circuit, CircuitOpenError, CircuitState

logger = get_logger()


def _setup_gcp_credentials() -> None:
    """Set up GCP credentials from environment JSON."""
    creds_json = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")
    if creds_json and not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        # Write JSON to temp file and set env var
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(creds_json)
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = f.name
            logger.info("gcp_credentials_setup", path=f.name)


@dataclass
class GroundedResponse:
    """Response with grounding citations."""
    text: str
    citations: List[Dict[str, str]]  # [{title, url, snippet}]
    grounding_metadata: Optional[Dict] = None


@dataclass
class ResearchReport:
    """Deep research output."""
    title: str
    summary: str
    sections: List[Dict[str, str]]  # [{heading, content}]
    citations: List[Dict[str, str]]
    thinking_trace: List[str]  # reasoning steps
    query_count: int
    duration_seconds: float


class GeminiClient:
    """Gemini client with circuit breaker. Supports both API key and Vertex AI modes."""

    def __init__(self):
        self.project_id = os.environ.get("GCP_PROJECT_ID", "")
        self.location = os.environ.get("GCP_LOCATION", "us-central1")
        self.api_key = os.environ.get("GEMINI_API_KEY", "")
        self._client = None

        # Prefer API key (free tier), fall back to Vertex AI
        self.use_vertex = not self.api_key and bool(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON"))
        if self.use_vertex:
            _setup_gcp_credentials()
            logger.info("gemini_mode", mode="vertex_ai", project=self.project_id)
        elif self.api_key:
            logger.info("gemini_mode", mode="api_key")
        else:
            logger.warning("gemini_no_credentials")

    @property
    def client(self):
        """Lazy-load genai client."""
        if self._client is None:
            from google import genai
            if self.use_vertex:
                self._client = genai.Client(
                    vertexai=True,
                    project=self.project_id,
                    location=self.location
                )
            else:
                self._client = genai.Client(api_key=self.api_key)
        return self._client

    async def chat(
        self,
        messages: List[Dict],
        model: str = "gemini-2.0-flash-001",
        thinking_level: str = None,  # Only for models that support it (2.5+)
        tools: List[str] = None,
        max_tokens: int = 8192,
        stream: bool = False,
    ) -> Any:
        """Standard chat with optional thinking and tools.

        Args:
            messages: [{"role": "user", "content": "..."}]
            model: gemini-2.0-flash-001, gemini-2.5-flash-preview-05-20
            thinking_level: minimal, low, medium, high (only for 2.5+ models)
            tools: ["google_search", "code_execution"]
            stream: Return generator if True

        Returns:
            Text string or async generator
        """
        if gemini_circuit.state == CircuitState.OPEN:
            raise CircuitOpenError("gemini_api", gemini_circuit._cooldown_remaining())

        from google.genai import types

        # Build tools
        tool_configs = []
        if tools and "google_search" in tools:
            tool_configs.append(types.Tool(google_search=types.GoogleSearch()))
        if tools and "code_execution" in tools:
            tool_configs.append(types.Tool(code_execution=types.ToolCodeExecution()))

        # Build thinking config (only for 2.5+ models)
        thinking_config = None
        if thinking_level and "2.5" in model:
            thinking_config = types.ThinkingConfig(
                include_thoughts=False,
                thinking_level=thinking_level
            )

        config = types.GenerateContentConfig(
            max_output_tokens=max_tokens,
            tools=tool_configs if tool_configs else None,
            thinking_config=thinking_config,
        )

        # Convert messages to content
        contents = self._messages_to_contents(messages)

        try:
            if stream:
                return self._stream_response(model, contents, config)

            response = await self.client.aio.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )
            gemini_circuit._record_success()
            return response.text

        except Exception as e:
            gemini_circuit._record_failure(e)
            logger.error("gemini_chat_error", error=str(e)[:100])
            raise

    async def _stream_response(
        self, model: str, contents: List, config: Any
    ) -> AsyncGenerator[str, None]:
        """Async generator for streaming responses."""
        async for chunk in self.client.aio.models.generate_content_stream(
            model=model,
            contents=contents,
            config=config,
        ):
            if chunk.text:
                yield chunk.text
        gemini_circuit._record_success()

    def _messages_to_contents(self, messages: List[Dict]) -> List:
        """Convert chat messages to Gemini contents format."""
        from google.genai import types
        contents = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append(types.Content(
                role=role,
                parts=[types.Part(text=msg["content"])]
            ))
        return contents

    async def grounded_query(
        self,
        query: str,
        grounding_sources: List[str] = None,
        model: str = "gemini-2.0-flash-001",
    ) -> GroundedResponse:
        """Quick grounded answer with citations.

        Args:
            query: User query
            grounding_sources: ["google_search", "google_maps"]
            model: Model to use

        Returns:
            GroundedResponse with text and citations
        """
        if gemini_circuit.state == CircuitState.OPEN:
            raise CircuitOpenError("gemini_api", gemini_circuit._cooldown_remaining())

        from google.genai import types

        sources = grounding_sources or ["google_search"]
        tools = []
        if "google_search" in sources:
            tools.append(types.Tool(google_search=types.GoogleSearch()))

        config = types.GenerateContentConfig(
            tools=tools,
        )

        try:
            response = await self.client.aio.models.generate_content(
                model=model,
                contents=query,
                config=config,
            )
            gemini_circuit._record_success()

            # Extract citations from grounding metadata
            citations = []
            if hasattr(response, 'grounding_metadata') and response.grounding_metadata:
                for source in response.grounding_metadata.get('groundingSupports', []):
                    citations.append({
                        "title": source.get("segment", {}).get("text", ""),
                        "url": source.get("segment", {}).get("uri", ""),
                        "snippet": source.get("text", "")
                    })

            return GroundedResponse(
                text=response.text,
                citations=citations,
                grounding_metadata=getattr(response, 'grounding_metadata', None)
            )

        except Exception as e:
            gemini_circuit._record_failure(e)
            logger.error("gemini_grounded_error", error=str(e)[:100])
            raise

    async def deep_research(
        self,
        query: str,
        on_progress: Callable[[str], None] = None,
        max_iterations: int = 10,
        model: str = "gemini-2.0-flash-001",
    ) -> ResearchReport:
        """Agentic multi-step research with streaming progress.

        Args:
            query: Research topic
            on_progress: Callback for progress updates
            max_iterations: Max research iterations
            model: Model to use

        Returns:
            ResearchReport with sections and citations
        """
        start_time = time.time()

        if gemini_circuit.state == CircuitState.OPEN:
            raise CircuitOpenError("gemini_api", gemini_circuit._cooldown_remaining())

        from google.genai import types

        thinking_trace = []
        all_citations = []
        query_count = 0

        # Step 1: Decompose query into sub-queries
        if on_progress:
            on_progress("Analyzing research topic...")

        decompose_prompt = f"""You are a research planner. Break down this research topic into 3-5 specific sub-queries that can be searched:

Topic: {query}

Output as JSON array of strings, each a searchable query. Only output the JSON array, no explanation."""

        decompose_config = types.GenerateContentConfig()  # No thinking for 2.0 models

        try:
            response = await self.client.aio.models.generate_content(
                model=model,
                contents=decompose_prompt,
                config=decompose_config,
            )
            gemini_circuit._record_success()

            # Parse JSON from response, handle markdown code blocks
            response_text = response.text.strip()
            if response_text.startswith("```"):
                # Remove markdown code block
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1])

            sub_queries = json.loads(response_text)
            thinking_trace.append(f"Decomposed into {len(sub_queries)} sub-queries")

            if on_progress:
                on_progress(f"Planning {len(sub_queries)} research steps...")

        except Exception as e:
            gemini_circuit._record_failure(e)
            logger.error("decompose_error", error=str(e)[:100])
            sub_queries = [query]  # Fallback to single query

        # Step 2: Research each sub-query with grounding
        findings = []
        search_tool = types.Tool(google_search=types.GoogleSearch())

        for i, sq in enumerate(sub_queries[:max_iterations]):
            if on_progress:
                on_progress(f"Researching ({i+1}/{len(sub_queries)}): {sq[:50]}...")

            try:
                response = await self.client.aio.models.generate_content(
                    model=model,
                    contents=f"Research and provide detailed findings on: {sq}",
                    config=types.GenerateContentConfig(tools=[search_tool]),
                )
                gemini_circuit._record_success()
                query_count += 1

                findings.append({
                    "query": sq,
                    "content": response.text
                })

                # Extract citations
                if hasattr(response, 'grounding_metadata') and response.grounding_metadata:
                    for source in response.grounding_metadata.get('groundingSupports', []):
                        all_citations.append({
                            "title": source.get("segment", {}).get("text", ""),
                            "url": source.get("segment", {}).get("uri", ""),
                        })

                thinking_trace.append(f"Completed: {sq[:40]}")

            except Exception as e:
                logger.warning("subquery_error", query=sq[:40], error=str(e)[:50])
                thinking_trace.append(f"Failed: {sq[:40]} - {str(e)[:30]}")

        # Step 3: Synthesize findings into report
        if on_progress:
            on_progress("Synthesizing research report...")

        findings_text = "\n\n".join([
            f"### {f['query']}\n{f['content']}" for f in findings
        ])

        synthesize_prompt = f"""You are a research analyst. Synthesize these findings into a professional research report.

RESEARCH TOPIC: {query}

FINDINGS:
{findings_text}

Create a structured report with:
1. Executive Summary (2-3 paragraphs)
2. Key Findings (3-5 main points)
3. Detailed Analysis (expand on each finding)
4. Recommendations
5. Conclusion

Output as professional markdown."""

        try:
            response = await self.client.aio.models.generate_content(
                model=model,
                contents=synthesize_prompt,
                config=types.GenerateContentConfig(),  # No thinking for 2.0 models
            )
            gemini_circuit._record_success()

            report_text = response.text

        except Exception as e:
            gemini_circuit._record_failure(e)
            logger.error("synthesize_error", error=str(e)[:100])
            report_text = findings_text  # Fallback to raw findings

        duration = time.time() - start_time

        if on_progress:
            on_progress(f"Research complete in {duration:.0f}s")

        return ResearchReport(
            title=query,
            summary=report_text[:500] + "..." if len(report_text) > 500 else report_text,
            sections=[{"heading": "Full Report", "content": report_text}],
            citations=all_citations,
            thinking_trace=thinking_trace,
            query_count=query_count,
            duration_seconds=duration
        )

    async def analyze_image(
        self,
        image_base64: str,
        prompt: str,
        media_type: str = "image/jpeg",
        model: str = "gemini-2.0-flash-001",
    ) -> str:
        """Vision analysis of image.

        Args:
            image_base64: Base64 encoded image
            prompt: Analysis prompt
            media_type: MIME type
            model: Model to use

        Returns:
            Analysis text
        """
        if gemini_circuit.state == CircuitState.OPEN:
            raise CircuitOpenError("gemini_api", gemini_circuit._cooldown_remaining())

        from google.genai import types
        import base64

        try:
            response = await self.client.aio.models.generate_content(
                model=model,
                contents=[
                    types.Part.from_bytes(
                        data=base64.b64decode(image_base64),
                        mime_type=media_type
                    ),
                    prompt
                ],
            )
            gemini_circuit._record_success()
            return response.text

        except Exception as e:
            gemini_circuit._record_failure(e)
            logger.error("gemini_vision_error", error=str(e)[:100])
            raise


# Singleton
_client: Optional[GeminiClient] = None


def get_gemini_client() -> GeminiClient:
    """Get or create GeminiClient singleton."""
    global _client
    if _client is None:
        _client = GeminiClient()
    return _client
