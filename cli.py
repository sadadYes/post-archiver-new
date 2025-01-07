from scraper import scrape_community_posts, save_posts
from pathlib import Path
import argparse

def main():
    parser = argparse.ArgumentParser(description='YouTube Community Posts Scraper')
    parser.add_argument('channel_id', help='YouTube channel ID')
    parser.add_argument('-n', '--num-posts', type=int, default=float('inf'),
                      help='Number of posts to scrape (default: all)')
    parser.add_argument('-o', '--output', type=Path, default=Path.cwd(),
                      help='Output directory (default: current directory)')
    
    args = parser.parse_args()
    
    try:
        # Scrape posts
        posts = scrape_community_posts(args.channel_id, args.num_posts)
        
        # Save posts
        output_file = save_posts(posts, args.channel_id, args.output)
        
        print(f"\nSuccessfully scraped {len(posts)} posts")
        print(f"Results saved to: {output_file}")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return 1
    
    return 0

if __name__ == '__main__':
    exit(main())
