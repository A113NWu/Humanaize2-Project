"""
Humanaize Web Search Skill
Search the web for information
"""

import re
import json
from typing import Dict, Any, Optional
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


def execute(input_data: Any) -> Dict:
    """
    Execute web search

    Args:
        input_data: Either a search query string or dict with 'query' key

    Returns:
        Dict with search results or error
    """
    if not REQUESTS_AVAILABLE:
        return {
            "success": False,
            "error": "requests library not installed. Install with: pip install requests"
        }

    if isinstance(input_data, dict):
        query = input_data.get("query", "")
        num_results = input_data.get("num_results", 5)
        safe_search = input_data.get("safe_search", True)
    else:
        query = str(input_data)
        num_results = 5
        safe_search = True

    if not query:
        return {
            "success": False,
            "error": "No search query provided"
        }

    try:
        results = _search_ddg(query, num_results=num_results, safe_search=safe_search)
        return {
            "success": True,
            "query": query,
            "results": results,
            "count": len(results)
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Search failed: {str(e)}",
            "query": query
        }


def _search_ddg(query: str, num_results: int = 5, safe_search: bool = True) -> list:
    """
    Search using DuckDuckGo HTML interface

    Args:
        query: Search query
        num_results: Number of results to return
        safe_search: Enable safe search

    Returns:
        List of search results with title, url, and snippet
    """
    params = {
        "q": query,
        "kl": "wt-wt",
        "ia": "web"
    }

    if safe_search:
        params["ia"] = "web"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "en-US,en;q=0.9"
    }

    response = requests.get(
        "https://html.duckduckgo.com/html/",
        params=params,
        headers=headers,
        timeout=10
    )

    if response.status_code != 200:
        raise Exception(f"HTTP {response.status_code}")

    results = []
    html = response.text

    result_pattern = r'<a class="result__a" href="([^"]+)"[^>]*>([^<]+)</a>'
    snippet_pattern = r'<a class="result__snippet"[^>]*>([^<]+)</a>'

    matches = re.findall(result_pattern, html)
    snippets = re.findall(snippet_pattern, html)

    for i, (url, title) in enumerate(matches[:num_results]):
        title = _clean_html(title)
        snippet = _clean_html(snippets[i]) if i < len(snippets) else ""

        results.append({
            "title": title,
            "url": url,
            "snippet": snippet
        })

    return results


def _clean_html(text: str) -> str:
    """Remove HTML tags and decode entities"""
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('&amp;', '&')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&quot;', '"')
    text = text.replace('&#39;', "'")
    text = text.replace('&nbsp;', ' ')
    return text.strip()


def search_image(query: str, num_images: int = 5) -> Dict:
    """
    Search for images

    Args:
        query: Search query
        num_images: Number of images to return

    Returns:
        Dict with image results
    """
    if not REQUESTS_AVAILABLE:
        return {
            "success": False,
            "error": "requests library not installed"
        }

    try:
        params = {
            "q": query,
            "t": "image",
            "ia": "images"
        }

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        response = requests.get(
            "https://html.duckduckgo.com/html/",
            params=params,
            headers=headers,
            timeout=10
        )

        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}")

        html = response.text
        img_pattern = r'src="(https?://[^"]+\.(?:jpg|jpeg|png|gif|webp))"'
        matches = re.findall(img_pattern, html, re.IGNORECASE)

        images = [{"url": url, "query": query} for url in matches[:num_images]]

        return {
            "success": True,
            "query": query,
            "images": images,
            "count": len(images)
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
