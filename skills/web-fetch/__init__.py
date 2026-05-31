"""
Humanaize Web Fetch Skill
Fetch content from URLs
"""

import re
from typing import Dict, Any
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


def execute(input_data: Any) -> Dict:
    """
    Fetch content from a URL

    Args:
        input_data: Either a URL string or dict with 'url' key

    Returns:
        Dict with fetched content or error
    """
    if not REQUESTS_AVAILABLE:
        return {
            "success": False,
            "error": "requests library not installed. Install with: pip install requests"
        }

    if isinstance(input_data, dict):
        url = input_data.get("url", "")
        method = input_data.get("method", "GET")
        headers = input_data.get("headers", {})
        timeout = input_data.get("timeout", 30)
        max_length = input_data.get("max_length", 50000)
    else:
        url = str(input_data)
        method = "GET"
        headers = {}
        timeout = 30
        max_length = 50000

    if not url:
        return {
            "success": False,
            "error": "No URL provided"
        }

    if not url.startswith(("http://", "https://")):
        return {
            "success": False,
            "error": "Invalid URL. Must start with http:// or https://"
        }

    default_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9"
    }
    default_headers.update(headers)

    try:
        response = requests.request(
            method=method,
            url=url,
            headers=default_headers,
            timeout=timeout,
            allow_redirects=True
        )

        content = response.text

        if len(content) > max_length:
            content = content[:max_length] + f"\n... [Truncated {len(content) - max_length} characters]"

        return {
            "success": True,
            "url": url,
            "final_url": response.url,
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "content": content,
            "content_length": len(content),
            "encoding": response.encoding
        }

    except requests.exceptions.Timeout:
        return {
            "success": False,
            "error": f"Request timed out after {timeout} seconds",
            "url": url
        }
    except requests.exceptions.ConnectionError:
        return {
            "success": False,
            "error": "Failed to connect to the server",
            "url": url
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "url": url
        }


def fetch_json(input_data: Any) -> Dict:
    """
    Fetch and parse JSON from a URL

    Args:
        input_data: URL string or dict with 'url' key

    Returns:
        Dict with parsed JSON or error
    """
    if isinstance(input_data, dict):
        url = input_data.get("url", "")
    else:
        url = str(input_data)

    result = execute({"url": url})

    if not result["success"]:
        return result

    try:
        json_data = result.get("content", "")
        if isinstance(json_data, str):
            import json
            parsed = json.loads(json_data)
        else:
            parsed = json_data

        return {
            "success": True,
            "url": url,
            "data": parsed
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to parse JSON: {str(e)}",
            "url": url
        }


def extract_links(html_content: str, base_url: str = "") -> Dict:
    """
    Extract all links from HTML content

    Args:
        html_content: HTML string
        base_url: Base URL for resolving relative links

    Returns:
        Dict with list of links
    """
    if not html_content:
        return {
            "success": False,
            "error": "No HTML content provided"
        }

    link_pattern = r'href=["\']([^"\']+)["\']'
    links = re.findall(link_pattern, html_content)

    absolute_links = []
    for link in links:
        if link.startswith(("http://", "https://", "/")):
            absolute_links.append(link)

    return {
        "success": True,
        "links": absolute_links,
        "count": len(absolute_links)
    }


def extract_text(html_content: str) -> str:
    """
    Extract plain text from HTML

    Args:
        html_content: HTML string

    Returns:
        Plain text content
    """
    text = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    text = text.replace('\xa0', ' ')
    return text.strip()
