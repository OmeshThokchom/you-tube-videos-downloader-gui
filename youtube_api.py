import os
from googleapiclient.discovery import build
from dotenv import load_dotenv
import isodate

class YouTubeManager:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("YOUTUBE_API_KEY")
        if not self.api_key:
            print("Warning: YOUTUBE_API_KEY not found in .env")
            # In a real app, we might raise an error or prompt the user
            
        self.youtube = None
        if self.api_key:
            self.youtube = build('youtube', 'v3', developerKey=self.api_key)

    def get_channel_videos(self, channel_id_or_handle):
        """
        Fetches all videos from a channel's 'uploads' playlist.
        Returns a list of dictionaries with video details.
        """
        if not self.youtube:
            raise ValueError("YouTube API Key is missing.")

        try:
            # 1. Parse Input (Handle URL or ID)
            import re
            channel_input = channel_id_or_handle.strip()
            
            # Regex to extract handle from URL (e.g. https://youtube.com/@Handle)
            handle_match = re.search(r'(?:https?://)?(?:www\.)?youtube\.com/(?:@)([a-zA-Z0-9_.-]+)', channel_input)
            if handle_match:
                channel_input = '@' + handle_match.group(1)
            elif 'youtube.com/channel/' in channel_input:
                channel_input = channel_input.split('/channel/')[-1].split('/')[0]
            
            # 2. Resolve Handle to Channel ID
            channel_id = channel_input
            if channel_input.startswith('@'):
                request = self.youtube.search().list(
                    part="snippet",
                    q=channel_input,
                    type="channel",
                    maxResults=1
                )
                response = request.execute()
                if 'items' not in response:
                     raise ValueError(f"API Error: 'items' key missing in search response. Response: {response}")
                if not response['items']:
                    raise ValueError(f"Channel handle '{channel_input}' not found.")
                channel_id = response['items'][0]['snippet']['channelId']

            # 3. Get Channel Details (Uploads Playlist ID)
            request = self.youtube.channels().list(
                part="contentDetails,snippet",
                id=channel_id
            )
            response = request.execute()
            
            if 'items' not in response:
                 raise ValueError(f"API Error: 'items' key missing in channels response. Response: {response}")
            
            if not response['items']:
                raise ValueError(f"Channel ID '{channel_id}' not found.")

            uploads_playlist_id = response['items'][0]['contentDetails']['relatedPlaylists']['uploads']
            channel_title = response['items'][0]['snippet']['title']

            # 2. Fetch Playlist Items
            videos = []
            next_page_token = None
            
            while True:
                pl_request = self.youtube.playlistItems().list(
                    part="snippet,contentDetails",
                    playlistId=uploads_playlist_id,
                    maxResults=50,
                    pageToken=next_page_token
                )
                pl_response = pl_request.execute()

                for item in pl_response['items']:
                    video_id = item['contentDetails']['videoId']
                    title = item['snippet']['title']
                    published_at = item['snippet']['publishedAt']
                    thumbnail = item['snippet']['thumbnails'].get('high', {}).get('url')
                    
                    videos.append({
                        'id': video_id,
                        'title': title,
                        'published_at': published_at,
                        'thumbnail': thumbnail,
                        'channel': channel_title
                    })

                next_page_token = pl_response.get('nextPageToken')
                if not next_page_token:
                    break
            
            return videos

        except Exception as e:
            raise e

if __name__ == "__main__":
    # Test
    yt = YouTubeManager()
    # Replace with a valid ID for testing if key is present
    # print(yt.get_channel_videos("UC_x5XG1OV2P6uZZ5FSM9Ttw")) 
    pass
