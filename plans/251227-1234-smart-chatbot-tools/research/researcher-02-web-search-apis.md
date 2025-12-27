# Web Search APIs for AI Chatbots Research

## API Comparison (2025)

| Feature | Tavily | Serper/SerpAPI | Brave Search |
|---------|--------|----------------|--------------|
| Focus | AI Agents & RAG | Raw SERP data | Privacy-first |
| Format | LLM-ready JSON | Titles/URLs | Summaries |
| Strength | Deep extraction | Speed/cost | Independent index |
| Use Case | Research, RAG | Factual lookups | Privacy apps |
| Pricing | Premium | Cheap | Free tier |

## Recommended: Tavily

### Why Tavily for AI Agents
1. **Context-Optimized** - Returns clean, structured JSON without ads/navigation
2. **Built-in Tools** - Includes crawl/extract for full page content
3. **LLM Integration** - Native support in LangChain, LlamaIndex
4. **RAG-Focused** - Designed for retrieval-augmented generation

### Tavily API Usage
```python
from tavily import TavilyClient

client = TavilyClient(api_key="tvly-xxx")

# Basic search
result = client.search(
    query="latest AI developments",
    search_depth="advanced",  # or "basic"
    max_results=5
)

# Returns structured context
for r in result["results"]:
    print(r["title"], r["url"], r["content"])
```

### Pricing
- Free: 1000 searches/month
- Pro: $50/month for 10K searches

## Alternative: Serper (Budget Option)

### Serper API Usage
```python
import requests

response = requests.post(
    "https://google.serper.dev/search",
    headers={"X-API-Key": "xxx"},
    json={"q": "query"}
)
results = response.json()["organic"]
```

### Pricing
- Free: 2500 queries/month
- $50/month for 50K queries

## Implementation Strategy

1. **Primary**: Tavily for complex research queries
2. **Fallback**: Serper for simple factual lookups
3. **Caching**: Cache results for repeated queries (15min TTL)

## Integration Pattern
```python
async def web_search(query: str) -> dict:
    """Tool function for Claude to call."""
    client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    result = client.search(query=query, max_results=5)

    # Format for LLM consumption
    formatted = []
    for r in result["results"]:
        formatted.append(f"**{r['title']}**\n{r['content']}\nSource: {r['url']}")

    return {"results": "\n\n".join(formatted)}
```

## Key Takeaways
- Tavily best for AI agents due to LLM-ready output
- Serper good budget alternative with post-processing
- Brave for privacy-sensitive applications
