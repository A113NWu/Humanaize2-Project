"""
Humanaize Web Search Skill
Search the web for information

搜索结果会先做清洗：丢掉广告/跳转链接、按相关度和来源去重排序，
再自动用 web-fetch 抓取最靠前的几个网页，把正文一起返回。
"""

import os
import re
import sys
import json
import html as _html
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Optional
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# 明显的广告/跳转/追踪域名，直接丢掉
_JUNK_HOSTS = (
    "pos.baidu.com", "cpro.baidu.com", "eclick.baidu.com", "googleadservices.com",
    "doubleclick.net", "googlesyndication.com", "adclick", "ads.",
)
# 无法还原真实地址的跳转链接（拿到也读不到内容）
_JUNK_URL_MARKS = (
    "/link?url=", "bing.com/ck/a", "so.com/link?", "sogou.com/link?",
    "baidu.com/baidu.php", "google.com/url?",
)
# 分享/追踪参数，去重时剥掉
_TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "spm", "from", "share_source", "share_medium", "share_plat",
    "share_session_id", "share_tag", "timestamp", "unique_k", "scene",
}


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
        fetch_pages = input_data.get("fetch_pages", 2)
        fetch_max_chars = input_data.get("fetch_max_chars", 3000)
    else:
        query = str(input_data)
        num_results = 5
        safe_search = True
        engine = "auto"
        fetch_pages = 2
        fetch_max_chars = 3000

    query = _clean_query(query)
    if not query:
        return {
            "success": False,
            "error": "No search query provided"
        }

    try:
        results = _search(query, num_results=num_results, safe_search=safe_search, engine=engine)
        fetched = _fetch_pages(results, fetch_pages, fetch_max_chars)
        payload = {
            "success": True,
            "query": query,
            "results": results,
            "count": len(results),
            "fetched_pages": fetched,
            "engine": results[0].get('source', 'unknown') if results else 'unknown'
        }
        if not results:
            payload["note"] = "没有找到相关结果，换一个更具体的关键词再试"
        return payload

    except Exception as e:
        return {
            "success": False,
            "error": f"Search failed: {str(e)}",
            "query": query
        }


def _clean_query(query: str) -> str:
    """压平空白、去掉包裹的标点和引号，限制长度。"""
    text = re.sub(r"\s+", " ", str(query or "")).strip()
    return text.strip("，。！？!?；;、\"'“”‘’")[:120]


def _normalize_url(url: str) -> str:
    """去重用的规范化：去掉协议/www/追踪参数/末尾斜杠。"""
    try:
        parsed = urllib.parse.urlparse(url or "")
    except Exception:
        return ""
    if not parsed.netloc:
        return ""
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    query = [
        (k, v) for k, v in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        if k.lower() not in _TRACKING_PARAMS
    ]
    path = parsed.path.rstrip("/")
    return host + path + ("?" + urllib.parse.urlencode(query) if query else "")


def _query_terms(query: str) -> set:
    """查询词：拉丁词 + 中文二元组；短查询退回单字。"""
    q = (query or "").lower()
    latin = re.findall(r"[a-z0-9_+.-]{2,}", q)
    cjk = re.findall(r"[\u4e00-\u9fff]", q)
    bigrams = [cjk[i] + cjk[i + 1] for i in range(len(cjk) - 1)]
    terms = set(latin) | set(bigrams)
    return terms or set(cjk)


def _is_junk(result: dict) -> bool:
    url = str(result.get("url") or "")
    low = url.lower()
    if not low.startswith(("http://", "https://")):
        return True
    if any(mark in low for mark in _JUNK_URL_MARKS):
        return True
    host = urllib.parse.urlparse(low).netloc
    if any(junk in host for junk in _JUNK_HOSTS):
        return True
    title = str(result.get("title") or "")
    if re.search(r"(广告|推广|赞助)$", title):
        return True
    return False


def _dedupe_rank(results: list, query: str, num_results: int) -> list:
    """丢掉广告/跳转链接，按标题/摘要相关度排序，同域名内容只留最相关的一条。"""
    terms = _query_terms(query)
    seen, cleaned = set(), []
    for item in results:
        if not isinstance(item, dict) or _is_junk(item):
            continue
        key = _normalize_url(item.get("url", "")) or item.get("url", "")
        if key in seen:
            continue
        seen.add(key)
        score = 0
        title = str(item.get("title") or "").lower()
        snippet = str(item.get("snippet") or "").lower()
        for term in terms:
            if term in title:
                score += 3
            if term in snippet:
                score += 1
        item["_score"] = score if terms else 1
        cleaned.append(item)

    if terms:
        # 一个查询词都对不上的结果不要——宁可返回空，也不把奇怪的东西塞给她
        cleaned = [item for item in cleaned if item["_score"] > 0]
    cleaned.sort(key=lambda item: (-item.get("_score", 0),
                                   0 if item.get("source") == "Bing" else 1))
    for item in cleaned:
        item.pop("_score", None)
    return cleaned[:max(1, int(num_results))]


def _load_web_fetch():
    """按文件路径加载同目录的 web-fetch 技能（兼容开发态与打包态）。"""
    import importlib.util
    roots = [os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
    if getattr(sys, "frozen", False):
        roots.insert(0, os.path.join(os.path.dirname(sys.executable), "skills"))
    for root in roots:
        init = os.path.join(root, "web-fetch", "__init__.py")
        if not os.path.exists(init):
            continue
        try:
            spec = importlib.util.spec_from_file_location("skills_web_fetch", init)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        except Exception:
            continue
    return None


def _fetch_pages(results: list, count, max_chars) -> int:
    """用 web-fetch 抓取排名靠前的网页，把正文挂到结果的 content 字段。"""
    try:
        limit = max(0, min(int(count or 0), 5))
        chars = max(200, min(int(max_chars or 3000), 20000))
    except Exception:
        limit, chars = 2, 3000
    targets = [item for item in results[:limit]
               if str(item.get("url") or "").startswith(("http://", "https://"))]
    if not targets:
        return 0
    fetch_mod = _load_web_fetch()

    def _work(item):
        try:
            if fetch_mod is not None:
                res = fetch_mod.execute({"url": item["url"], "timeout": 12,
                                         "max_length": chars * 4})
                if not res.get("success"):
                    item["fetch_error"] = res.get("error") or "fetch failed"
                    return False
                text = fetch_mod.extract_text(res.get("content") or "")
            else:
                res = requests.get(item["url"], timeout=12, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                                  "Chrome/120.0 Safari/537.36"})
                res.raise_for_status()
                text = extract_text(res.text)
            text = re.sub(r"\s+", " ", text).strip()
            if text:
                item["content"] = text[:chars]
                item["fetched"] = True
                return True
            item["fetch_error"] = "empty content"
        except Exception as exc:
            item["fetch_error"] = f"{type(exc).__name__}: {exc}"[:120]
        return False

    done = 0
    with ThreadPoolExecutor(max_workers=min(3, len(targets))) as pool:
        for ok in pool.map(_work, targets):
            done += 1 if ok else 0
    return done


def extract_text(html_content: str) -> str:
    """web-fetch 不可用时的兜底：去掉脚本/样式/标签，保留正文。"""
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html_content, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    return text.replace("\xa0", " ")


def _search(query: str, num_results: int = 5, safe_search: bool = True, engine: str = "auto") -> list:
    """按引擎顺序收集，多个引擎互补；再统一清洗、去重、排序。"""
    engines = []
    if engine == "auto":
        engines = ["bing", "ddg", "baidu"]
    elif engine in ("baidu", "bing", "ddg"):
        engines = [engine]
    else:
        engines = ["bing", "ddg", "baidu"]

    collected = []
    for engine_name in engines:
        try:
            if engine_name == "baidu":
                part = _search_baidu(query, num_results)
            elif engine_name == "bing":
                part = _search_bing(query, num_results)
            else:
                part = _search_ddg(query, num_results, safe_search)
        except Exception as e:
            print(f"[WARN] {engine_name} search failed: {e}")
            continue
        # 这个引擎的结果先清洗；没有一条相关就换下一个，不把奇怪的结果塞进去
        collected = _dedupe_rank(part, query, num_results)
        if len(collected) >= num_results:
            break
        if collected:
            break   # 已有相关结果，少量也比掺进不相关的强

    if not collected:
        return []
    return _dedupe_rank(collected, query, num_results)


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


def _search_bing_rss(query: str, num_results: int = 5) -> list:
    """Bing RSS 接口：稳定、无广告位，比 HTML 结构可靠。"""
    params = {"q": query, "format": "rss", "count": num_results, "setlang": "zh-CN"}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    response = requests.get("https://cn.bing.com/search", params=params,
                            headers=headers, timeout=10)
    if response.status_code != 200:
        raise Exception(f"HTTP {response.status_code}")
    response.encoding = response.apparent_encoding or "utf-8"
    results = []
    for item in re.findall(r"<item>(.*?)</item>", response.text, re.DOTALL)[:num_results]:
        title_match = re.search(r"<title>(.*?)</title>", item, re.DOTALL)
        link_match = re.search(r"<link>(.*?)</link>", item, re.DOTALL)
        desc_match = re.search(r"<description>(.*?)</description>", item, re.DOTALL)
        title = _clean_html(title_match.group(1)) if title_match else ""
        url = _clean_html(link_match.group(1)) if link_match else ""
        snippet = _clean_html(desc_match.group(1)) if desc_match else ""
        if title and url.startswith("http"):
            results.append({"title": title, "url": url, "snippet": snippet, "source": "Bing"})
    return results


def _search_bing(query: str, num_results: int = 5) -> list:
    """
    Search using Bing. 先用 RSS 接口（稳定、无广告），失败再退回 HTML 解析。
    """
    try:
        results = _search_bing_rss(query, num_results)
        if results:
            return results
    except Exception as e:
        print(f"[WARN] bing rss failed: {e}")

    params = {
        "q": query,
        "count": num_results,
        "first": 1,
        "setlang": "zh-CN",
        "cc": "CN"
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
    }

    response = requests.get(
        "https://cn.bing.com/search",
        params=params,
        headers=headers,
        timeout=10
    )

    if response.status_code != 200:
        raise Exception(f"HTTP {response.status_code}")

    response.encoding = response.apparent_encoding or response.encoding
    results = []
    html = response.text

    result_container_pattern = r'<li[^>]*class="[^"]*b_algo[^"]*"[^>]*>(.*?)</li>'
    containers = re.findall(result_container_pattern, html, re.DOTALL)

    def _extract(container):
        title_match = re.search(r'<h2[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', container, re.DOTALL)
        if not title_match:
            return None
        url = _decode_bing_url(title_match.group(1))
        title = _clean_html(title_match.group(2))
        snippet_match = re.search(r'<p[^>]*>(.*?)</p>', container, re.DOTALL)
        snippet = _clean_html(snippet_match.group(1)) if snippet_match else ""
        if url and title:
            return {"title": title, "url": url, "snippet": snippet, "source": "Bing"}
        return None

    for container in containers[:num_results * 2]:
        item = _extract(container)
        if item and item not in results:
            results.append(item)
        if len(results) >= num_results:
            break

    return results


def _decode_bing_url(url: str) -> str:
    """把必应跳转链接 bing.com/ck/a?...&u=a1<base64> 还原成真实 URL。"""
    if not url or "bing.com/ck/a" not in url or "u=" not in url:
        return url
    try:
        qs = urllib.parse.urlparse(url).query
        params = urllib.parse.parse_qs(qs)
        u = params.get("u", [""])[0]
        # u 参数形如 a1aHR0cHM...（前缀 a1 + base64url 编码的真实地址）
        if u[:2] in ("a1", "a2"):
            import base64
            raw = u[2:]
            raw += "=" * (-len(raw) % 4)
            real = base64.urlsafe_b64decode(raw).decode("utf-8", "ignore")
            if real.startswith("http"):
                return real
    except Exception:
        pass
    return url



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
    """去掉标签/CDATA 并还原 HTML 实体。"""
    text = re.sub(r"<!\[CDATA\[|\]\]>", "", str(text or ""))
    text = re.sub(r"<[^>]+>", "", text)
    return _html.unescape(text).strip()


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
