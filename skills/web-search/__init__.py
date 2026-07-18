"""
Humanaize Web Search Skill
Search the web for information
"""

import re
import json
import urllib.parse
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
        engine = input_data.get("engine", "auto")
    else:
        query = str(input_data)
        num_results = 5
        safe_search = True
        engine = "auto"

    if not query:
        return {
            "success": False,
            "error": "No search query provided"
        }

    try:
        results = _search(query, num_results=num_results, safe_search=safe_search, engine=engine)
        return {
            "success": True,
            "query": query,
            "results": results,
            "count": len(results),
            "engine": results[0].get('source', 'unknown') if results else 'unknown'
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Search failed: {str(e)}",
            "query": query
        }


def _search(query: str, num_results: int = 5, safe_search: bool = True, engine: str = "auto") -> list:
    """
    Search using available search engines with fallback

    Args:
        query: Search query
        num_results: Number of results to return
        safe_search: Enable safe search
        engine: Search engine to use ("auto", "baidu", "bing", "ddg")

    Returns:
        List of search results with title, url, snippet, and source
    """
    engines = []
    
    if engine == "auto":
        engines = ["bing", "baidu", "ddg"]
    elif engine == "baidu":
        engines = ["baidu"]
    elif engine == "bing":
        engines = ["bing"]
    elif engine == "ddg":
        engines = ["ddg"]
    else:
        engines = ["baidu", "bing", "ddg"]
    
    for engine_name in engines:
        try:
            if engine_name == "baidu":
                return _search_baidu(query, num_results)
            elif engine_name == "bing":
                return _search_bing(query, num_results)
            elif engine_name == "ddg":
                return _search_ddg(query, num_results, safe_search)
        except Exception as e:
            print(f"[WARN] {engine_name} search failed: {e}")
            continue
    
    raise Exception("All search engines failed")


def _search_baidu(query: str, num_results: int = 5) -> list:
    """
    Search using Baidu HTML interface

    Args:
        query: Search query
        num_results: Number of results to return

    Returns:
        List of search results with title, url, snippet, and source
    """
    params = {
        "wd": query,
        "pn": 0,
        "rn": num_results
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8"
    }

    response = requests.get(
        "https://www.baidu.com/s",
        params=params,
        headers=headers,
        timeout=10,
        allow_redirects=True
    )

    if response.status_code != 200:
        raise Exception(f"HTTP {response.status_code}")

    results = []
    html = response.text

    result_container_pattern = r'<div[^>]*class="[^"]*result[^"]*"[^>]*>(.*?)</div>'
    containers = re.findall(result_container_pattern, html, re.DOTALL)

    for container in containers[:num_results]:
        title_pattern = r'<h3[^>]*><a[^>]+href="([^"]+)"[^>]*>(.*?)</a></h3>'
        title_match = re.search(title_pattern, container, re.DOTALL)
        
        snippet_pattern = r'<span[^>]*class="[^"]*content-right[^"]*"[^>]*>(.*?)</span>'
        snippet_match = re.search(snippet_pattern, container, re.DOTALL)

        if title_match:
            url = title_match.group(1)
            title = _clean_html(title_match.group(2))
            snippet = _clean_html(snippet_match.group(1)) if snippet_match else ""

            if url.startswith('/link?url='):
                try:
                    url = urllib.parse.unquote(url.replace('/link?url=', ''))
                except:
                    pass

            if url and title:
                results.append({
                    "title": title,
                    "url": url,
                    "snippet": snippet,
                    "source": "Baidu"
                })

    if not results:
        result_pattern = r'<h3[^>]*><a[^>]+href="([^"]+)"[^>]*>(.*?)</a></h3>'
        matches = re.findall(result_pattern, html, re.DOTALL)
        
        for i, (url, title) in enumerate(matches[:num_results]):
            title = _clean_html(title)
            
            snippet_pattern = r'<span[^>]*class="[^"]*content-right[^"]*"[^>]*>(.*?)</span>'
            snippet_matches = re.findall(snippet_pattern, html, re.DOTALL)
            snippet = _clean_html(snippet_matches[i]) if i < len(snippet_matches) else ""

            if url.startswith('/link?url='):
                try:
                    url = urllib.parse.unquote(url.replace('/link?url=', ''))
                except:
                    pass

            if url and title:
                results.append({
                    "title": title,
                    "url": url,
                    "snippet": snippet,
                    "source": "Baidu"
                })

    return results


def _search_bing(query: str, num_results: int = 5) -> list:
    """
    Search using Bing HTML interface

    Args:
        query: Search query
        num_results: Number of results to return

    Returns:
        List of search results with title, url, snippet, and source
    """
    params = {
        "q": query,
        "count": num_results,
        "first": 1
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9"
    }

    response = requests.get(
        "https://www.bing.com/search",
        params=params,
        headers=headers,
        timeout=10
    )

    if response.status_code != 200:
        raise Exception(f"HTTP {response.status_code}")

    results = []
    html = response.text

    result_container_pattern = r'<li[^>]*class="[^"]*b_algo[^"]*"[^>]*>(.*?)</li>'
    containers = re.findall(result_container_pattern, html, re.DOTALL)

    for container in containers[:num_results]:
        title_pattern = r'<h2[^>]*><a[^>]+href="([^"]+)"[^>]*>(.*?)</a></h2>'
        title_match = re.search(title_pattern, container, re.DOTALL)
        
        snippet_pattern = r'<p[^>]*class="[^"]*b_lineclamp[^"]*"[^>]*>(.*?)</p>'
        snippet_match = re.search(snippet_pattern, container, re.DOTALL)

        if title_match:
            url = title_match.group(1)
            title = _clean_html(title_match.group(2))
            snippet = _clean_html(snippet_match.group(1)) if snippet_match else ""

            if url and title:
                results.append({
                    "title": title,
                    "url": url,
                    "snippet": snippet,
                    "source": "Bing"
                })

    if not results:
        result_pattern = r'<h2[^>]*><a[^>]+href="([^"]+)"[^>]*>(.*?)</a></h2>'
        snippet_pattern = r'<p[^>]*class="[^"]*b_lineclamp[^"]*"[^>]*>(.*?)</p>'
        
        matches = re.findall(result_pattern, html, re.DOTALL)
        snippets = re.findall(snippet_pattern, html, re.DOTALL)

        for i, (url, title) in enumerate(matches[:num_results]):
            title = _clean_html(title)
            snippet = _clean_html(snippets[i]) if i < len(snippets) else ""

            if url and title:
                results.append({
                    "title": title,
                    "url": url,
                    "snippet": snippet,
                    "source": "Bing"
                })

    return results


def _search_ddg(query: str, num_results: int = 5, safe_search: bool = True) -> list:
    """
    Search using DuckDuckGo HTML interface

    Args:
        query: Search query
        num_results: Number of results to return
        safe_search: Enable safe search

    Returns:
        List of search results with title, url, snippet, and source
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
            "snippet": snippet,
            "source": "DuckDuckGo"
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
