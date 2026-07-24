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
        Perform a web search using DuckDuckGo API
        Returns list of results with title, snippet, and URL
        """
        try:
            # Use curl to query DuckDuckGo API
            import urllib.parse
            encoded_query = urllib.parse.quote(query)
            
            # DuckDuckGo Instant Answer API
            url = f"https://api.duckduckgo.com/?q={encoded_query}&format=json&pretty=1"
            
            try:
                import requests
                
                # 使用系统代理（如果配置了）
                proxies = None
                http_proxy = os.environ.get('http_proxy') or os.environ.get('HTTP_PROXY')
                https_proxy = os.environ.get('https_proxy') or os.environ.get('HTTPS_PROXY')
                if http_proxy or https_proxy:
                    proxies = {
                        'http': http_proxy,
                        'https': https_proxy
                    }
                
                response = requests.get(url, timeout=15, proxies=proxies)
                data = response.json()
            except ImportError:
                # Fallback to curl if requests is not available
                curl_cmd = ['curl', '-s', '-L', url]
                http_proxy = os.environ.get('http_proxy') or os.environ.get('HTTP_PROXY')
                if http_proxy:
                    curl_cmd.extend(['--proxy', http_proxy])
                result = subprocess.run(
                    curl_cmd,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode != 0:
                    return self._get_fallback_results(query)
                data = json.loads(result.stdout)
            
            results = []
            
            # Extract results from DuckDuckGo API
            if 'RelatedTopics' in data:
                for topic in data['RelatedTopics'][:max_results]:
                    if 'Text' in topic and 'FirstURL' in topic:
                        results.append({
                            'title': topic.get('Text', '')[:100],
                            'snippet': topic.get('Text', '')[:200],
                            'url': topic.get('FirstURL', ''),
                            'source': 'DuckDuckGo'
                        })
            
            # If no results from RelatedTopics, check Abstract
            if len(results) == 0 and 'Abstract' in data and data['Abstract']:
                results.append({
                    'title': data.get('Heading', query),
                    'snippet': data.get('Abstract', '')[:300],
                    'url': data.get('AbstractURL', ''),
                    'source': 'DuckDuckGo'
                })
                
            # Add to history
            self.search_history.append({
                'query': query,
                'timestamp': datetime.now().isoformat(),
                'result_count': len(results)
            })
            
            # Keep only last 100 searches
            if len(self.search_history) > 100:
                self.search_history = self.search_history[-100:]
                
            self._save_history()
            
            return results
            
        except Exception as e:
            # 记录详细错误以便调试，但使用简化的错误信息
            error_str = str(e)
            if 'Network is unreachable' in error_str or 'Connection refused' in error_str:
                print(f"[WARN] Web search unavailable (network error). Using fallback response.")
            elif 'timed out' in error_str:
                print(f"[WARN] Web search timeout. Using fallback response.")
            else:
                print(f"[ERROR] Web search failed: {e}")
            return self._get_fallback_results(query)
            
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
        Determine if the user's message requires a web search
        Returns True if search is needed
        """
        message_lower = user_message.lower()
        
        # Keywords that indicate need for search
        search_triggers = [
            '最新', '最新消息', '最新资讯', '最新动态', '最新进展',
            '今天', '现在', '最近', '目前', '当前',
            '新闻', '资讯', '报道', '发布',
            '多少', '什么', '哪个', '谁', '何时', '哪里',
            'how', 'what', 'when', 'where', 'who', 'which', 'latest',
            'news', 'update', 'today', 'now', 'current', 'recent'
        ]
        
        # Check for explicit questions
        question_patterns = [
            r'什么是.*', r'.*是什么',
            r'怎么.*', r'.*怎么办',
            r'为什么.*', r'.*为什么',
            r'如何.*', r'.*如何',
            r'是否.*', r'.*是否',
            r'有哪些.*', r'.*有哪些',
            r'谁.*', r'.*是谁',
            r'何时.*', r'.*何时',
            r'哪里.*', r'.*哪里',
            r'how.*', r'what.*', r'why.*', r'when.*', r'where.*'
        ]
        
        # Check if message contains search triggers
        for trigger in search_triggers:
            if trigger in message_lower:
                return True
                
        # Check for question patterns
        for pattern in question_patterns:
            if re.search(pattern, message_lower):
                return True
                
        # Check for specific topics that need up-to-date info
        time_sensitive_topics = [
            '天气', '股票', '股价', '汇率', '新闻',
            '比赛', '比分', '赛事', '体育',
            '疫情', '新冠', '政策', '法规',
            '发布会', '新品', '发布', '上市',
            'weather', 'stock', 'news', 'sports', 'match'
        ]
        
        for topic in time_sensitive_topics:
            if topic in message_lower:
                return True
                
        return False
        
    def get_search_history(self, limit=10):
        """Get recent search history"""
        return self.search_history[-limit:]
        
    def clear_history(self):
        """Clear search history"""
        self.search_history = []
        self._save_history()
