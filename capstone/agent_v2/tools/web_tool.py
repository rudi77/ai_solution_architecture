# ============================================
# WEB TOOLS
# ============================================

import asyncio
import re
from typing import Any, Dict
import aiohttp
from capstone.agent_v2.tool import Tool


class WebSearchTool(Tool):
    """Web search using DuckDuckGo (no API key required)"""
    
    @property
    def name(self) -> str:
        return "web_search"
    
    @property
    def description(self) -> str:
        return "Search the web using DuckDuckGo"
    
    async def execute(self, query: str, num_results: int = 5, **kwargs) -> Dict[str, Any]:
        if not aiohttp:
            return {"success": False, "error": "aiohttp not installed"}
        
        try:
            async with aiohttp.ClientSession() as session:
                params = {
                    "q": query,
                    "format": "json",
                    "no_html": "1",
                    "skip_disambig": "1"
                }
                
                async with session.get(
                    "https://api.duckduckgo.com/",
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    # DuckDuckGo may return a non-standard JSON Content-Type (e.g., application/x-javascript)
                    # Allow json() to parse regardless of Content-Type to avoid ContentTypeError.
                    data = await response.json(content_type=None)
                    
                    results = []
                    
                    # Extract abstract if available
                    if data.get("Abstract"):
                        results.append({
                            "title": data.get("Heading", ""),
                            "snippet": data["Abstract"],
                            "url": data.get("AbstractURL", "")
                        })
                    
                    # Extract related topics
                    for topic in data.get("RelatedTopics", [])[:num_results]:
                        if isinstance(topic, dict) and "Text" in topic:
                            results.append({
                                "title": topic.get("Text", "").split(" - ")[0][:50],
                                "snippet": topic.get("Text", ""),
                                "url": topic.get("FirstURL", "")
                            })
                    
                    return {
                        "success": True,
                        "query": query,
                        "results": results[:num_results],
                        "count": len(results)
                    }
                    
        except Exception as e:
            return {"success": False, "error": str(e)}
            

class WebFetchTool(Tool):
    """Fetch content from URLs"""
    
    @property
    def name(self) -> str:
        return "web_fetch"
    
    @property
    def description(self) -> str:
        return "Fetch and extract content from a URL"
    
    async def execute(self, url: str, **kwargs) -> Dict[str, Any]:
        if not aiohttp:
            return {"success": False, "error": "aiohttp not installed"}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as response:
                    content = await response.text()
                    
                    # Simple HTML extraction
                    if "text/html" in response.headers.get("Content-Type", ""):
                        # Remove HTML tags (basic)
                        text = re.sub('<script[^>]*>.*?</script>', '', content, flags=re.DOTALL)
                        text = re.sub('<style[^>]*>.*?</style>', '', content, flags=re.DOTALL)
                        text = re.sub('<[^>]+>', '', text)
                        text = ' '.join(text.split())[:5000]  # Limit size
                    else:
                        text = content[:5000]
                    
                    return {
                        "success": True,
                        "url": url,
                        "status": response.status,
                        "content": text,
                        "content_type": response.headers.get("Content-Type", ""),
                        "length": len(content)
                    }
                    
        except asyncio.TimeoutError:
            return {"success": False, "error": "Request timed out"}
        except Exception as e:
            return {"success": False, "error": str(e)}