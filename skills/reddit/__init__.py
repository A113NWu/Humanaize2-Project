"""
Reddit浏览技能
让Aize可以浏览和搜索Reddit论坛内容
"""

import json
import os
import time
from typing import Dict, Any, Optional

try:
    import praw
    PRAW_AVAILABLE = True
except ImportError:
    PRAW_AVAILABLE = False

CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'config.json')

class RedditSkill:
    def __init__(self):
        self.config = self._load_config()
        self.reddit = None
        self._init_reddit()
    
    def _load_config(self) -> Dict:
        """加载配置文件"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {
            'client_id': '',
            'client_secret': '',
            'user_agent': 'Humanaize/1.0',
            'mock_mode': True
        }
    
    def _save_config(self):
        """保存配置文件"""
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.config, f, indent=2)
        except:
            pass
    
    def _init_reddit(self):
        """初始化Reddit连接"""
        if not PRAW_AVAILABLE:
            return
        
        if self.config['client_id'] and self.config['client_secret']:
            try:
                self.reddit = praw.Reddit(
                    client_id=self.config['client_id'],
                    client_secret=self.config['client_secret'],
                    user_agent=self.config['user_agent']
                )
                self.reddit.read_only = True
            except Exception as e:
                print(f"[WARN] Failed to initialize Reddit: {e}")
                self.reddit = None
    
    def configure(self, params: Dict) -> Dict:
        """配置Reddit API"""
        if 'client_id' in params:
            self.config['client_id'] = params['client_id']
        if 'client_secret' in params:
            self.config['client_secret'] = params['client_secret']
        if 'user_agent' in params:
            self.config['user_agent'] = params['user_agent']
        if 'mock_mode' in params:
            self.config['mock_mode'] = params['mock_mode']
        
        self._save_config()
        
        if not self.config['mock_mode']:
            self._init_reddit()
            if self.reddit:
                try:
                    self.reddit.user.me()
                    return {"success": True, "message": "配置成功，连接测试通过"}
                except:
                    return {"success": False, "message": "配置成功，但无法验证连接"}
        
        return {"success": True, "message": "配置成功"}
    
    def _get_mock_posts(self, count: int = 10) -> list:
        """获取模拟帖子数据"""
        return [
            {
                'title': f'Mock Post {i+1}: AI Technology Advances',
                'url': f'https://reddit.com/r/technology/comments/mock{i+1}',
                'subreddit': 'technology',
                'score': 1000 + i * 100,
                'num_comments': 100 + i * 10,
                'author': f'user{i+1}',
                'created': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time() - i * 3600))
            }
            for i in range(count)
        ]
    
    def get_hot_posts(self, limit: int = 10) -> Dict:
        """获取热门帖子"""
        if self.config['mock_mode']:
            return {
                "success": True,
                "action": "hot",
                "results": self._get_mock_posts(limit)
            }
        
        if not self.reddit:
            return {"success": False, "error": "Reddit未配置或连接失败"}
        
        try:
            results = []
            for submission in self.reddit.front.hot(limit=limit):
                results.append({
                    'title': submission.title,
                    'url': submission.url,
                    'subreddit': str(submission.subreddit),
                    'score': submission.score,
                    'num_comments': submission.num_comments,
                    'author': str(submission.author) if submission.author else '[deleted]',
                    'created': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(submission.created_utc))
                })
            
            return {
                "success": True,
                "action": "hot",
                "results": results
            }
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_new_posts(self, limit: int = 10) -> Dict:
        """获取新帖子"""
        if self.config['mock_mode']:
            return {
                "success": True,
                "action": "new",
                "results": self._get_mock_posts(limit)
            }
        
        if not self.reddit:
            return {"success": False, "error": "Reddit未配置或连接失败"}
        
        try:
            results = []
            for submission in self.reddit.front.new(limit=limit):
                results.append({
                    'title': submission.title,
                    'url': submission.url,
                    'subreddit': str(submission.subreddit),
                    'score': submission.score,
                    'num_comments': submission.num_comments,
                    'author': str(submission.author) if submission.author else '[deleted]',
                    'created': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(submission.created_utc))
                })
            
            return {
                "success": True,
                "action": "new",
                "results": results
            }
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_top_posts(self, limit: int = 10, time_filter: str = 'day') -> Dict:
        """获取置顶帖子"""
        if self.config['mock_mode']:
            return {
                "success": True,
                "action": "top",
                "results": self._get_mock_posts(limit)
            }
        
        if not self.reddit:
            return {"success": False, "error": "Reddit未配置或连接失败"}
        
        try:
            results = []
            for submission in self.reddit.front.top(limit=limit, time_filter=time_filter):
                results.append({
                    'title': submission.title,
                    'url': submission.url,
                    'subreddit': str(submission.subreddit),
                    'score': submission.score,
                    'num_comments': submission.num_comments,
                    'author': str(submission.author) if submission.author else '[deleted]',
                    'created': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(submission.created_utc))
                })
            
            return {
                "success": True,
                "action": "top",
                "results": results
            }
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def search_posts(self, query: str, limit: int = 10) -> Dict:
        """搜索帖子"""
        if self.config['mock_mode']:
            return {
                "success": True,
                "action": "search",
                "query": query,
                "results": self._get_mock_posts(limit)
            }
        
        if not self.reddit:
            return {"success": False, "error": "Reddit未配置或连接失败"}
        
        try:
            results = []
            for submission in self.reddit.search(query, limit=limit):
                results.append({
                    'title': submission.title,
                    'url': submission.url,
                    'subreddit': str(submission.subreddit),
                    'score': submission.score,
                    'num_comments': submission.num_comments,
                    'author': str(submission.author) if submission.author else '[deleted]',
                    'created': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(submission.created_utc))
                })
            
            return {
                "success": True,
                "action": "search",
                "query": query,
                "results": results
            }
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def browse_subreddit(self, name: str, sort: str = 'hot', limit: int = 10) -> Dict:
        """浏览子版块"""
        if self.config['mock_mode']:
            return {
                "success": True,
                "action": "subreddit",
                "subreddit": name,
                "results": self._get_mock_posts(limit)
            }
        
        if not self.reddit:
            return {"success": False, "error": "Reddit未配置或连接失败"}
        
        try:
            subreddit = self.reddit.subreddit(name)
            results = []
            
            if sort == 'hot':
                submissions = subreddit.hot(limit=limit)
            elif sort == 'new':
                submissions = subreddit.new(limit=limit)
            elif sort == 'top':
                submissions = subreddit.top(limit=limit)
            else:
                submissions = subreddit.hot(limit=limit)
            
            for submission in submissions:
                results.append({
                    'title': submission.title,
                    'url': submission.url,
                    'subreddit': str(submission.subreddit),
                    'score': submission.score,
                    'num_comments': submission.num_comments,
                    'author': str(submission.author) if submission.author else '[deleted]',
                    'created': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(submission.created_utc))
                })
            
            return {
                "success": True,
                "action": "subreddit",
                "subreddit": name,
                "results": results
            }
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_comments(self, url: str, limit: int = 10) -> Dict:
        """获取帖子评论"""
        if self.config['mock_mode']:
            mock_comments = [
                {
                    'author': f'user{i+1}',
                    'body': f'这是第{i+1}条模拟评论，内容关于AI技术讨论。',
                    'score': 100 + i * 10,
                    'created': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time() - i * 300))
                }
                for i in range(limit)
            ]
            return {
                "success": True,
                "action": "comments",
                "url": url,
                "results": mock_comments
            }
        
        if not self.reddit:
            return {"success": False, "error": "Reddit未配置或连接失败"}
        
        try:
            submission = self.reddit.submission(url=url)
            submission.comments.replace_more(limit=0)
            
            results = []
            for comment in submission.comments[:limit]:
                results.append({
                    'author': str(comment.author) if comment.author else '[deleted]',
                    'body': comment.body[:200] + '...' if len(comment.body) > 200 else comment.body,
                    'score': comment.score,
                    'created': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(comment.created_utc))
                })
            
            return {
                "success": True,
                "action": "comments",
                "url": url,
                "results": results
            }
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_status(self) -> Dict:
        """获取Reddit状态"""
        return {
            "success": True,
            "praw_available": PRAW_AVAILABLE,
            "configured": bool(self.config['client_id'] and self.config['client_secret']),
            "connected": self.reddit is not None,
            "mock_mode": self.config['mock_mode'],
            "user_agent": self.config['user_agent']
        }

_reddit_skill = RedditSkill()

def execute(input_data: Any) -> Dict:
    """
    执行Reddit浏览技能
    
    Args:
        input_data: 技能输入数据
    
    Returns:
        执行结果
    """
    if not PRAW_AVAILABLE:
        return {"success": False, "error": "praw库未安装，请运行: pip install praw"}
    
    if isinstance(input_data, dict):
        action = input_data.get('action', '')
        params = input_data.get('params', {})
    else:
        return {"success": False, "error": "无效的输入格式"}
    
    if action == 'configure':
        return _reddit_skill.configure(params)
    elif action == 'hot':
        limit = params.get('limit', 10)
        return _reddit_skill.get_hot_posts(limit)
    elif action == 'new':
        limit = params.get('limit', 10)
        return _reddit_skill.get_new_posts(limit)
    elif action == 'top':
        limit = params.get('limit', 10)
        time_filter = params.get('time_filter', 'day')
        return _reddit_skill.get_top_posts(limit, time_filter)
    elif action == 'search':
        query = params.get('query', '')
        limit = params.get('limit', 10)
        if not query:
            return {"success": False, "error": "缺少必要参数: query"}
        return _reddit_skill.search_posts(query, limit)
    elif action == 'subreddit':
        name = params.get('name', '')
        sort = params.get('sort', 'hot')
        limit = params.get('limit', 10)
        if not name:
            return {"success": False, "error": "缺少必要参数: name"}
        return _reddit_skill.browse_subreddit(name, sort, limit)
    elif action == 'comments':
        url = params.get('url', '')
        limit = params.get('limit', 10)
        if not url:
            return {"success": False, "error": "缺少必要参数: url"}
        return _reddit_skill.get_comments(url, limit)
    elif action == 'status':
        return _reddit_skill.get_status()
    else:
        return {"success": False, "error": f"未知的动作: {action}"}