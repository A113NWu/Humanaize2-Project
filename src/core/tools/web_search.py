"""
Web Search Tool
Enables AI to search the internet for information.
"""

import subprocess
import json
import re
from datetime import datetime
import os

class WebSearch:
    def __init__(self):
        self.search_history = []
        self._load_history()
        
    def _load_history(self):
        """Load search history from file"""
        history_path = os.path.join(os.path.dirname(__file__), 'search_history.json')
        if os.path.exists(history_path):
            try:
                with open(history_path, 'r') as f:
                    self.search_history = json.load(f)
            except:
                self.search_history = []
                
    def _save_history(self):
        """Save search history to file"""
        history_path = os.path.join(os.path.dirname(__file__), 'search_history.json')
        try:
            with open(history_path, 'w') as f:
                json.dump(self.search_history, f, indent=2)
        except:
            pass
            
    def search(self, query, max_results=5):
        """
        Perform a web search using Bing (国内可访问)
        Returns list of results with title, snippet, and URL
        """
        try:
            import urllib.parse
            import re as _re
            encoded_query = urllib.parse.quote(query)

            # 必应搜索（国内可访问，中文支持好）
            url = f"https://cn.bing.com/search?q={encoded_query}"

            try:
                import requests

                proxies = None
                http_proxy = os.environ.get('http_proxy') or os.environ.get('HTTP_PROXY')
                https_proxy = os.environ.get('https_proxy') or os.environ.get('HTTPS_PROXY')
                if http_proxy or https_proxy:
                    proxies = {
                        'http': http_proxy,
                        'https': https_proxy
                    }

                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml',
                    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                }
                response = requests.get(url, timeout=15, proxies=proxies, headers=headers)
                html = response.text
            except ImportError:
                curl_cmd = ['curl', '-s', '-L', url,
                            '-H', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                            '-H', 'Accept-Language: zh-CN,zh;q=0.9']
                http_proxy = os.environ.get('http_proxy') or os.environ.get('HTTP_PROXY')
                if http_proxy:
                    curl_cmd.extend(['--proxy', http_proxy])
                result = subprocess.run(
                    curl_cmd, capture_output=True, text=True, timeout=30
                )
                if result.returncode != 0:
                    return self._get_fallback_results(query)
                html = result.stdout

            results = []
            # 必应结果结构：<li class="b_algo"><h2><a href="URL">标题</a></h2><p>摘要</p></li>
            for m in _re.finditer(
                r'<li[^>]*class="b_algo"[^>]*>(.*?)</li>',
                html, _re.S
            ):
                block = m.group(1)
                # 标题和链接
                title_m = _re.search(r'<h2[^>]*>\s*<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', block, _re.S)
                if not title_m:
                    continue
                href = title_m.group(1)
                title = _re.sub(r'<[^>]+>', '', title_m.group(2)).strip()
                # 摘要
                snip_m = _re.search(r'<p[^>]*>(.*?)</p>', block, _re.S)
                snippet = _re.sub(r'<[^>]+>', '', snip_m.group(1)).strip() if snip_m else ''
                if title and href and not href.startswith('javascript:'):
                    results.append({
                        'title': title[:100],
                        'snippet': (snippet or title)[:300],
                        'url': href,
                        'source': 'Bing'
                    })
                if len(results) >= max_results:
                    break

            # 如果必应没拿到结果，回退 DuckDuckGo Instant Answer API
            if not results:
                results = self._instant_answer_search(query, max_results)

            self.search_history.append({
                'query': query,
                'timestamp': datetime.now().isoformat(),
                'result_count': len(results)
            })
            if len(self.search_history) > 100:
                self.search_history = self.search_history[-100:]
            self._save_history()

            return results

        except Exception as e:
            error_str = str(e)
            if 'Network is unreachable' in error_str or 'Connection refused' in error_str:
                print(f"[WARN] Web search unavailable (network error). Using fallback response.")
            elif 'timed out' in error_str:
                print(f"[WARN] Web search timeout. Using fallback response.")
            else:
                print(f"[ERROR] Web search failed: {e}")
            return self._get_fallback_results(query)

    def _instant_answer_search(self, query, max_results=5):
        """兜底：DuckDuckGo Instant Answer API（中文效果差，仅作后备）"""
        try:
            import urllib.parse
            import requests
            encoded_query = urllib.parse.quote(query)
            url = f"https://api.duckduckgo.com/?q={encoded_query}&format=json&pretty=1"
            proxies = None
            http_proxy = os.environ.get('http_proxy') or os.environ.get('HTTP_PROXY')
            https_proxy = os.environ.get('https_proxy') or os.environ.get('HTTPS_PROXY')
            if http_proxy or https_proxy:
                proxies = {'http': http_proxy, 'https': https_proxy}
            response = requests.get(url, timeout=15, proxies=proxies)
            data = response.json()
            results = []
            if 'RelatedTopics' in data:
                for topic in data['RelatedTopics'][:max_results]:
                    if isinstance(topic, dict) and 'Text' in topic and 'FirstURL' in topic:
                        results.append({
                            'title': topic.get('Text', '')[:100],
                            'snippet': topic.get('Text', '')[:200],
                            'url': topic.get('FirstURL', ''),
                            'source': 'DuckDuckGo'
                        })
            if not results and 'Abstract' in data and data['Abstract']:
                results.append({
                    'title': data.get('Heading', query),
                    'snippet': data.get('Abstract', '')[:300],
                    'url': data.get('AbstractURL', ''),
                    'source': 'DuckDuckGo'
                })
            return results
        except Exception:
            return []
            
    def _get_fallback_results(self, query):
        """Get fallback results when API fails"""
        return [
            {
                'title': f"搜索结果暂时不可用",
                'snippet': f"由于网络原因，无法获取 '{query}' 的搜索结果。请检查网络连接，或稍后再试。",
                'url': f"https://duckduckgo.com/?q={query}",
                'source': 'Fallback'
            }
        ]
        
    def summarize_results(self, query, results):
        """Summarize search results into a concise response"""
        if not results:
            return f"抱歉，关于 '{query}' 的搜索没有找到结果。"
            
        summary = f"我找到了关于 '{query}' 的以下信息：\n\n"
        
        for i, result in enumerate(results[:3], 1):
            summary += f"{i}. **{result['title']}**\n"
            summary += f"   {result['snippet']}\n"
            if result['url']:
                summary += f"   来源: {result['url']}\n"
            summary += "\n"
        
        summary += "如需更详细的信息，我可以帮您深入搜索特定方面。"
        
        return summary
        
    def needs_search(self, user_message):
        """
        Determine if the user's message requires a web search.
        只對時效性強或明確要求搜索的內容觸發；常識/歷史/文化類問題直接讓 LLM 回答。
        """
        message_lower = user_message.lower()

        # 1) 用戶明確要求搜索 → 必搜
        explicit_search = ['搜索', '搜一下', '搜尋', '查一下', '查詢', '幫我查', '上网查', '上網查',
                           'search', 'look up', 'google', 'baidu']
        for kw in explicit_search:
            if kw in message_lower:
                return True

        # 2) 強時效性話題 → 必搜
        time_sensitive_topics = [
            '天气', '天氣', '股票', '股价', '股價', '汇率', '匯率', '新闻', '新聞',
            '比赛', '比賽', '比分', '賽事', '体育', '體育',
            '疫情', '新冠', '政策', '法规', '法規',
            '发布会', '發佈會', '新品', '上市', '开盘', '收盤',
            'weather', 'stock', 'news', 'sports', 'match', 'score',
            '币价', '幣價', 'crypto', '比特幣', '比特币', '房价', '房價'
        ]
        for topic in time_sensitive_topics:
            if topic in message_lower:
                return True

        # 3) 明確的時間限定詞 → 必搜
        time_triggers = ['最新', '今天', '現在', '最近', '目前', '当前', '當前',
                         '今日', '昨日', '明天', '本周', '本月', '今年',
                         'latest', 'today', 'now', 'current', 'recent', 'just now']
        for t in time_triggers:
            if t in message_lower:
                return True

        # 4) 定义性问题（"什么是X"、"谁是X"、"X是什么"）→ 不自动搜索，LLM 训练数据足够
        #    常识、历史、科学、文化类问题直接回答
        definition_patterns = [
            r'什么是', r'什麼是', r'是什么', r'是什麼',
            r'谁是', r'誰是', r'是谁', r'是誰',
            r'介绍一下', r'介紹一下', r'解释', r'解釋',
            r'意思', r'含义', r'含義', r'定义', r'定義'
        ]
        is_definition = any(re.search(p, message_lower) for p in definition_patterns)
        if is_definition:
            return False

        # 5) 其他疑问词（怎么、如何、为什么等）→ 不自动搜索
        #    让 LLM 自己判断是否需要调用 web-search 技能

        return False
        
    def get_search_history(self, limit=10):
        """Get recent search history"""
        return self.search_history[-limit:]
        
    def clear_history(self):
        """Clear search history"""
        self.search_history = []
        self._save_history()
