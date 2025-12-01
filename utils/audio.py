import asyncio
import functools
import yt_dlp
import discord
import re
import aiohttp
import urllib.parse

# Suppress noise from youtube_dl and bug reports
yt_dlp.utils.bug_reports_message = lambda *args, **kwargs: ''

async def fetch_better_metadata(title, artist=None):
    try:
        search_queries = []
        # Clean title
        clean_title = re.sub(r'[\\(\\[](official|video|lyrics|audio|mv|hq).*?[\\)\\]]', '', title, flags=re.IGNORECASE).strip()
        search_queries.append(clean_title)
        
        if artist:
            # Clean artist (remove "Topic", "Official", etc)
            clean_artist = re.sub(r'(Topic|Official|VEVO|Channel)', '', artist, flags=re.IGNORECASE).strip()
            if clean_artist and clean_artist.lower() not in clean_title.lower():
                search_queries.append(f"{clean_artist} {clean_title}")

        async with aiohttp.ClientSession() as session:
            for query in reversed(search_queries): # Try most specific first (Artist + Title)
                encoded_query = urllib.parse.quote(query)
                async with session.get(f"https://itunes.apple.com/search?term={encoded_query}&media=music&limit=1") as response:
                    if response.status == 200:
                        # iTunes returns text/javascript sometimes, so we disable content_type check
                        data = await response.json(content_type=None)
                        if data['results']:
                            item = data['results'][0]
                            # Verify similarity
                            found_title = item.get('trackName', '').lower()
                            found_artist = item.get('artistName', '').lower()
                            
                            # Basic check: Title must be somewhat similar
                            # We check if the search query words are in the found title
                            # or if the found title is in the search query
                            clean_query = query.lower()
                            
                            # If we have an artist, check if it matches too
                            if artist:
                                clean_artist_input = artist.lower()
                                if clean_artist_input not in found_artist and found_artist not in clean_artist_input:
                                    continue # Artist mismatch, try next or fallback

                            # Title check (loose)
                            # If the found title is completely different, skip
                            # Simple heuristic: Check if at least one significant word matches
                            # or if it's a substring
                            if clean_title.lower() not in found_title and found_title not in clean_title.lower():
                                # One last check: Levenshtein distance or similar would be better, 
                                # but for now let's just be conservative.
                                # If the query was "Just disappear" and result is "Sayonara Elegy", this catches it.
                                continue

                            return {
                                'artwork': item.get('artworkUrl100', '').replace('100x100', '600x600'),
                                'title': item.get('trackName'),
                                'artist': item.get('artistName')
                            }
            
            # Fallback to Deezer
            for query in reversed(search_queries):
                encoded_query = urllib.parse.quote(query)
                async with session.get(f"https://api.deezer.com/search?q={encoded_query}&limit=1") as response:
                    if response.status == 200:
                        data = await response.json(content_type=None)
                        if data.get('data'):
                            item = data['data'][0]
                            
                            # Verify similarity (Deezer)
                            found_title = item.get('title', '').lower()
                            found_artist = item.get('artist', {}).get('name', '').lower()
                            clean_query = query.lower()

                            if artist:
                                clean_artist_input = artist.lower()
                                if clean_artist_input not in found_artist and found_artist not in clean_artist_input:
                                    continue

                            if clean_title.lower() not in found_title and found_title not in clean_title.lower():
                                continue

                            album = item.get('album', {})
                            art = album.get('cover_xl') or album.get('cover_big') or album.get('cover_medium')
                            return {
                                'artwork': art,
                                'title': item.get('title'),
                                'artist': item.get('artist', {}).get('name')
                            }

    except Exception as e:
        print(f"Metadata fetch error: {e}")
    return None

class YTDLSource(discord.PCMVolumeTransformer):
    YTDL_OPTIONS = {
        'format': 'bestaudio/best',
        'extractaudio': True,
        'audioformat': 'mp3',
        'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
        'restrictfilenames': True,
        'noplaylist': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'logtostderr': False,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'auto',
        'source_address': '0.0.0.0',
        'cookiefile': 'cookies.txt', # Use cookies to bypass sign-in
    }

    FFMPEG_OPTIONS = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn',
    }

    ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

    def __init__(self, source, *, data, volume=0.5, requester=None):
        super().__init__(source, volume)
        self.requester = requester
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.webpage_url = data.get('webpage_url')
        self.duration = data.get('duration')
        self.uploader = data.get('uploader')
        self.thumbnail = data.get('thumbnail')

    @property
    def formatted_duration(self):
        if not self.duration:
            return "Unknown"
        seconds = int(self.duration)
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True, requester=None):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: cls.ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else cls.ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **cls.FFMPEG_OPTIONS), data=data, requester=requester)

    @classmethod
    async def create_source(cls, search: str, *, loop=None, requester=None, is_playlist_entry=False):
        loop = loop or asyncio.get_event_loop()
        
        partial = functools.partial(cls.ytdl.extract_info, search, download=False, process=False)
        data = await loop.run_in_executor(None, partial)

        if data is None:
            raise Exception("Could not find anything matching `{}`".format(search))

        sources = []
        entries = []

        if 'entries' in data:
            entries = list(data['entries'])
        else:
            entries = [data]

        # If it's a single entry request (is_playlist_entry=True), we just want one result
        if is_playlist_entry and entries:
            entries = [entries[0]]

        # Process the first entry fully (so we can play it immediately)
        # Process others as LazySource
        
        for i, entry in enumerate(entries):
            if i == 0:
                # Fully resolve the first one
                webpage_url = entry.get('webpage_url') or entry.get('url')
                partial = functools.partial(cls.ytdl.extract_info, webpage_url, download=False)
                processed_data = await loop.run_in_executor(None, partial)
                
                if 'entries' in processed_data:
                    processed_data = processed_data['entries'][0]

                # Try to get better artwork and metadata
                artist = processed_data.get('artist') or processed_data.get('uploader')
                metadata = await fetch_better_metadata(processed_data.get('title', search), artist)
                if metadata:
                    if metadata.get('artwork'):
                        processed_data['thumbnail'] = metadata['artwork']
                    if metadata.get('title'):
                        processed_data['title'] = metadata['title']
                    if metadata.get('artist'):
                        processed_data['uploader'] = metadata['artist']
                
                sources.append(cls(discord.FFmpegPCMAudio(processed_data['url'], **cls.FFMPEG_OPTIONS), data=processed_data, requester=requester))
            else:
                # Lazy load the rest
                sources.append(LazySource(entry, requester))
        
        return sources

class LazySource:
    def __init__(self, data, requester):
        self.data = data
        self.requester = requester
        self.title = data.get('title')
        self.url = data.get('url')
        self.webpage_url = data.get('webpage_url')
        self.duration = data.get('duration')
        self.uploader = data.get('uploader') or data.get('artist')
        self.thumbnail = data.get('thumbnail')

    @property
    def formatted_duration(self):
        if not self.duration:
            return "Unknown"
        seconds = int(self.duration)
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

    async def get_source(self, loop):
        # Resolve this lazy source into a real YTDLSource
        url = self.webpage_url or self.url
        return await YTDLSource.create_source(url, loop=loop, requester=self.requester, is_playlist_entry=True)

    @classmethod
    async def create_source(cls, search: str, *, loop=None, requester=None, is_playlist_entry=False):
        # This is a wrapper to keep the name consistent if needed, 
        # but actually we are modifying YTDLSource.create_source below.
        pass

# Monkey-patching or modifying YTDLSource.create_source directly in the file
# We will replace the existing create_source method in YTDLSource with the new logic.


def resolve_spotify_url(url: str) -> str:
    return url
