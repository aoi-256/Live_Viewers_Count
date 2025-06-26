"""
Live Viewers Count Monitor
YouTube と Twitch の同時接続数をリアルタイムで取得・記録するプログラム
"""

import csv
import time
import logging
import datetime
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import requests
import json

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('viewer_monitor.log')
    ]
)

logger = logging.getLogger(__name__)

def load_config(config_path: str = 'config.json') -> Dict:
    """設定ファイルを読み込み"""
    try:
        with open(config_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    except FileNotFoundError:
        logger.error(f"Configuration file {config_path} not found.")
        logger.error("Please copy config.example.json to config.json and set your API keys.")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in configuration file: {e}")
        raise

# 設定を読み込み
CONFIG = load_config()

class StreamerBase(ABC):
    """配信プラットフォームの基底クラス"""
    
    def __init__(self, name: str, url: str):
        self.name = name
        self.url = url
        self.platform = self.__class__.__name__.replace('Streamer', '').lower()
        
    @abstractmethod
    def get_viewer_count(self) -> int:
        """
        同時接続数を取得する抽象メソッド
        Returns:
            int: 同時接続数。取得失敗時は0を返す
        """
        pass
    
    def _log_attempt(self, success: bool, viewer_count: int = 0, error: str = ""):
        """取得試行をログに記録"""
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        status = "SUCCESS" if success else "FAILED"
        
        if success:
            logger.info(f"{timestamp} - {self.platform.upper()} - {self.name} - {status} - Viewers: {viewer_count}")
        else:
            logger.error(f"{timestamp} - {self.platform.upper()} - {self.name} - {status} - Error: {error}")

class YouTubeStreamer(StreamerBase):
    """YouTube配信の同時接続数取得クラス"""
    
    def __init__(self, name: str, url: str):
        super().__init__(name, url)
        self.video_id = self._extract_video_id(url)
        
    def _extract_video_id(self, url: str) -> Optional[str]:
        """YouTubeのURLから動画IDを抽出"""
        try:
            if 'youtube.com/watch?v=' in url:
                return url.split('v=')[1].split('&')[0]
            elif 'youtu.be/' in url:
                return url.split('youtu.be/')[1].split('?')[0]
            else:
                logger.error(f"Invalid YouTube URL format: {url}")
                return None
        except Exception as e:
            logger.error(f"Error extracting video ID from {url}: {str(e)}")
            return None
    
    def get_viewer_count(self) -> int:
        """YouTube Live配信の同時接続数を取得"""
        if not self.video_id:
            self._log_attempt(False, 0, "Invalid video ID")
            return 0
            
        try:
            api_url = "https://www.googleapis.com/youtube/v3/videos"
            params = {
                'part': 'liveStreamingDetails,snippet',
                'id': self.video_id,
                'key': CONFIG['youtube_api_key']
            }
            
            response = requests.get(api_url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if not data.get('items'):
                self._log_attempt(False, 0, "Video not found or not live")
                return 0
                
            video_data = data['items'][0]
            live_details = video_data.get('liveStreamingDetails', {})
            
            if 'concurrentViewers' not in live_details:
                self._log_attempt(False, 0, "Not a live stream or viewer count not available")
                return 0
                
            viewer_count = int(live_details['concurrentViewers'])
            self._log_attempt(True, viewer_count)
            return viewer_count
            
        except requests.exceptions.RequestException as e:
            self._log_attempt(False, 0, f"Network error: {str(e)}")
            return 0
        except (KeyError, ValueError, TypeError) as e:
            self._log_attempt(False, 0, f"Data parsing error: {str(e)}")
            return 0
        except Exception as e:
            self._log_attempt(False, 0, f"Unexpected error: {str(e)}")
            return 0

class TwitchStreamer(StreamerBase):
    """Twitch配信の同時接続数取得クラス"""
    
    def __init__(self, name: str, url: str):
        super().__init__(name, url)
        self.username = self._extract_username(url)
        
    def _extract_username(self, url: str) -> Optional[str]:
        """TwitchのURLからユーザー名を抽出"""
        try:
            if 'twitch.tv/' in url:
                # https://www.twitch.tv/username のパターン
                return url.split('twitch.tv/')[-1].split('?')[0].split('/')[0]
            else:
                logger.error(f"Invalid Twitch URL format: {url}")
                return None
        except Exception as e:
            logger.error(f"Error extracting username from {url}: {str(e)}")
            return None
    
    def get_viewer_count(self) -> int:
        """Twitch配信の同時接続数を取得"""
        if not self.username:
            self._log_attempt(False, 0, "Invalid username")
            return 0
            
        try:
            # Twitch APIヘッダー
            headers = {
                'Client-ID': CONFIG['twitch_client_id'],
                'Authorization': f"Bearer {CONFIG['twitch_access_token']}"
            }
            
            # ユーザー情報を取得してuser_idを入手
            user_url = "https://api.twitch.tv/helix/users"
            user_params = {'login': self.username}
            
            user_response = requests.get(user_url, headers=headers, params=user_params, timeout=10)
            user_response.raise_for_status()
            
            user_data = user_response.json()
            if not user_data.get('data'):
                self._log_attempt(False, 0, "User not found")
                return 0
                
            user_id = user_data['data'][0]['id']
            
            # 配信情報を取得
            streams_url = "https://api.twitch.tv/helix/streams"
            streams_params = {'user_id': user_id}
            
            streams_response = requests.get(streams_url, headers=headers, params=streams_params, timeout=10)
            streams_response.raise_for_status()
            
            streams_data = streams_response.json()
            
            if not streams_data.get('data'):
                self._log_attempt(False, 0, "Stream not live")
                return 0
                
            viewer_count = streams_data['data'][0]['viewer_count']
            self._log_attempt(True, viewer_count)
            return viewer_count
            
        except requests.exceptions.RequestException as e:
            self._log_attempt(False, 0, f"Network error: {str(e)}")
            return 0
        except (KeyError, ValueError, TypeError) as e:
            self._log_attempt(False, 0, f"Data parsing error: {str(e)}")
            return 0
        except Exception as e:
            self._log_attempt(False, 0, f"Unexpected error: {str(e)}")
            return 0

class ViewerCountMonitor:
    """視聴者数監視メインクラス"""
    
    def __init__(self):
        self.streamers: List[StreamerBase] = []
        self.output_file = CONFIG['output_file']
        self.headers_written = False
        
    def load_streams_from_csv(self, filename: str) -> bool:
        """CSVファイルから配信情報を読み込み"""
        try:
            with open(filename, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                
                for row in reader:
                    name = row['Name'].strip()
                    platform = int(row['platform'])
                    url = row['URL'].strip()
                    
                    if platform == 0:  # YouTube
                        streamer = YouTubeStreamer(name, url)
                    elif platform == 1:  # Twitch
                        streamer = TwitchStreamer(name, url)
                    else:
                        logger.warning(f"Unknown platform {platform} for {name}")
                        continue
                        
                    self.streamers.append(streamer)
                    logger.info(f"Loaded {streamer.platform} streamer: {name}")
                    
            logger.info(f"Successfully loaded {len(self.streamers)} streamers")
            return True
            
        except FileNotFoundError:
            logger.error(f"Input file {filename} not found")
            return False
        except Exception as e:
            logger.error(f"Error loading streams from CSV: {str(e)}")
            return False
    
    def collect_viewer_data(self) -> Dict[str, int]:
        """全ての配信から視聴者数を収集"""
        data = {}
        youtube_total = 0
        twitch_total = 0
        
        logger.info("Starting viewer count collection...")
        
        for streamer in self.streamers:
            viewer_count = streamer.get_viewer_count()
            data[streamer.name] = viewer_count
            
            if streamer.platform == 'youtube':
                youtube_total += viewer_count
            elif streamer.platform == 'twitch':
                twitch_total += viewer_count
        
        data['youtube_total'] = youtube_total
        data['twitch_total'] = twitch_total
        data['grand_total'] = youtube_total + twitch_total
        
        logger.info(f"Collection complete - YouTube: {youtube_total}, Twitch: {twitch_total}, Total: {data['grand_total']}")
        
        return data
    
    def write_to_csv(self, data: Dict[str, int]):
        """データをCSVファイルに書き込み"""
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # ヘッダーを準備
        headers = ['time', 'youtube', 'twitch'] + [streamer.name for streamer in self.streamers]
        
        # データ行を準備
        row = [
            timestamp,
            data['youtube_total'],
            data['twitch_total']
        ] + [data[streamer.name] for streamer in self.streamers]
        
        try:
            # ファイルが存在しない場合はヘッダーを書き込み
            file_exists = False
            try:
                with open(self.output_file, 'r'):
                    file_exists = True
            except FileNotFoundError:
                pass
            
            with open(self.output_file, 'a', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                
                if not file_exists:
                    writer.writerow(headers)
                    logger.info(f"Created new output file: {self.output_file}")
                
                writer.writerow(row)
                logger.info(f"Data written to {self.output_file}")
                
        except Exception as e:
            logger.error(f"Error writing to CSV: {str(e)}")
    
    def run(self):
        """メイン実行ループ"""
        logger.info("=== Live Viewers Count Monitor Started ===")
        logger.info(f"Input file: {CONFIG['input_file']}")
        logger.info(f"Output file: {CONFIG['output_file']}")
        logger.info(f"Check interval: {CONFIG['interval_seconds']} seconds")
        
        # 入力ファイルを読み込み
        if not self.load_streams_from_csv(CONFIG['input_file']):
            logger.error("Failed to load input file. Exiting.")
            return
        
        logger.info("Starting monitoring loop. Press Ctrl+C to stop.")
        
        try:
            while True:
                # データ収集
                data = self.collect_viewer_data()
                
                # CSV出力
                self.write_to_csv(data)
                
                # 次の実行まで待機
                logger.info(f"Waiting {CONFIG['interval_seconds']} seconds until next check...")
                time.sleep(CONFIG['interval_seconds'])
                
        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {str(e)}")


def main():
    """メイン関数"""
    monitor = ViewerCountMonitor()
    monitor.run()


if __name__ == "__main__":
    main()