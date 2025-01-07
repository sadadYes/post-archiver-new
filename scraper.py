import requests
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union, Any

class YouTubeCommunityAPI:
    def __init__(self):
        self.base_url = "https://www.youtube.com/youtubei/v1/browse"
        self.headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        self.client_context = {
            "client": {
                "hl": "en-GB",
                "clientName": "WEB",
                "clientVersion": "2.20241113.07.00"
            }
        }

    def _make_request(self, payload: Dict) -> Dict:
        """Make a POST request to YouTube API."""
        try:
            response = requests.post(self.base_url, json=payload, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise Exception(f"API request failed: {str(e)}")

    def get_initial_data(self, channel_id: str) -> Dict:
        """Get initial community tab data."""
        payload = {
            "context": self.client_context,
            "browseId": channel_id,
            "params": "Egljb21tdW5pdHnyBgQKAkoA"
        }
        return self._make_request(payload)

    def get_continuation_data(self, continuation_token: str) -> Dict:
        """Get next batch of posts using continuation token."""
        payload = {
            "context": self.client_context,
            "continuation": continuation_token
        }
        return self._make_request(payload)

class PostExtractor:
    @staticmethod
    def extract_text_content(content_runs: List[Dict]) -> str:
        """Extract text content from runs format."""
        return ''.join(run.get('text', '') for run in content_runs)

    @staticmethod
    def extract_post_data(post_renderer: Dict) -> Dict:
        """Extract relevant data from a post renderer."""
        post_data = {
            'post_id': post_renderer.get('postId', ''),
            'content': '',
            'timestamp': '',
            'likes': '0',
            'comments_count': '0',
            'images': [],
            'links': []
        }

        # Extract content text
        content_text = post_renderer.get('contentText', {})
        if 'runs' in content_text:
            post_data['content'] = PostExtractor.extract_text_content(content_text['runs'])
            
            # Extract links
            for run in content_text['runs']:
                if 'navigationEndpoint' in run:
                    url = run.get('navigationEndpoint', {}).get('commandMetadata', {}).get(
                        'webCommandMetadata', {}).get('url', '')
                    if url:
                        if url.startswith('/'):
                            url = f'https://www.youtube.com{url}'
                        post_data['links'].append({
                            'text': run.get('text', ''),
                            'url': url
                        })

        # Extract timestamp
        timestamp = post_renderer.get('publishedTimeText', {}).get('runs', [{}])[0].get('text', '')
        post_data['timestamp'] = timestamp

        # Extract likes
        vote_count = post_renderer.get('voteCount', {}).get('simpleText', '0')
        post_data['likes'] = vote_count

        # Extract comments count
        comment_count = post_renderer.get('actionButtons', {}).get('commentActionButtonsRenderer', {})\
            .get('replyButton', {}).get('buttonRenderer', {}).get('text', {}).get('simpleText', '0')
        post_data['comments_count'] = comment_count.split()[0] if comment_count else '0'

        # Extract images
        attachment = post_renderer.get('backstageAttachment', {})
        if 'backstageImageRenderer' in attachment:
            thumbnails = attachment['backstageImageRenderer']['image']['thumbnails']
            if thumbnails:
                # Get standard quality (usually the first one)
                standard_url = thumbnails[0]['url']
                
                # Get high quality by modifying the URL
                high_res_url = standard_url.split('=')[0] + '=s2160'
                
                post_data['images'].append({
                    'standard': standard_url,
                    'high_res': high_res_url
                })

        return post_data

def scrape_community_posts(channel_id: str, max_posts: int = float('inf')) -> List[Dict]:
    """Scrape community posts from a YouTube channel."""
    api = YouTubeCommunityAPI()
    posts = []
    
    # Get initial data
    response = api.get_initial_data(channel_id)
    
    try:
        # Find the Community tab
        tabs = response['contents']['twoColumnBrowseResultsRenderer']['tabs']
        community_tab = None
        for tab in tabs:
            if 'tabRenderer' in tab and \
               tab['tabRenderer'].get('title', '').lower() == 'community':
                community_tab = tab['tabRenderer']
                break
        
        if not community_tab:
            raise Exception("Community tab not found")
        
        # Extract initial posts
        contents = community_tab['content']['sectionListRenderer']['contents'][0]\
            ['itemSectionRenderer']['contents']
        
        # Get continuation token
        continuation_item = next(
            (item for item in contents if 'continuationItemRenderer' in item),
            None
        )
        token = continuation_item['continuationItemRenderer']['continuationEndpoint']\
            ['continuationCommand']['token'] if continuation_item else None
        
        # Process initial posts
        for content in contents:
            if 'backstagePostThreadRenderer' in content:
                post_renderer = content['backstagePostThreadRenderer']['post']['backstagePostRenderer']
                post_data = PostExtractor.extract_post_data(post_renderer)
                posts.append(post_data)
                
                if len(posts) >= max_posts:
                    return posts

        # Get remaining posts using continuation token
        while token and len(posts) < max_posts:
            response = api.get_continuation_data(token)
            
            # Extract posts from continuation data
            contents = response['onResponseReceivedEndpoints'][0]['appendContinuationItemsAction']\
                ['continuationItems']
            
            # Get next continuation token
            continuation_item = next(
                (item for item in contents if 'continuationItemRenderer' in item),
                None
            )
            token = continuation_item['continuationItemRenderer']['continuationEndpoint']\
                ['continuationCommand']['token'] if continuation_item else None
            
            # Process posts
            for content in contents:
                if 'backstagePostThreadRenderer' in content:
                    post_renderer = content['backstagePostThreadRenderer']['post']['backstagePostRenderer']
                    post_data = PostExtractor.extract_post_data(post_renderer)
                    posts.append(post_data)
                    
                    if len(posts) >= max_posts:
                        return posts

    except Exception as e:
        raise Exception(f"Failed to parse YouTube response: {str(e)}")

    return posts

def save_posts(posts: List[Dict], channel_id: str, output_dir: Optional[Path] = None) -> Path:
    """Save posts to a JSON file."""
    if not output_dir:
        output_dir = Path.cwd()
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = output_dir / f'posts_{channel_id}_{timestamp}.json'
    
    data = {
        'channel_id': channel_id,
        'scrape_date': datetime.now().isoformat(),
        'scrape_timestamp': int(datetime.now().timestamp()),
        'posts_count': len(posts),
        'posts': posts
    }
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    return filename 