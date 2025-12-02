import discord
from discord.ext import commands, tasks
from discord.ui import View, Button
import config
from utils.audio import YTDLSource, resolve_spotify_url
import asyncio
import traceback
import time

class DashboardView(View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="⏯️ Resume/Pause", style=discord.ButtonStyle.primary, custom_id="lyra:resume_pause")
    async def resume_pause(self, interaction: discord.Interaction, button: Button):
        await self.cog.toggle_pause(interaction)

    @discord.ui.button(label="⏭️ Skip", style=discord.ButtonStyle.success, custom_id="lyra:skip")
    async def skip(self, interaction: discord.Interaction, button: Button):
        await self.cog.skip_track(interaction)

    @discord.ui.button(label="⏹️ Stop", style=discord.ButtonStyle.danger, custom_id="lyra:stop")
    async def stop(self, interaction: discord.Interaction, button: Button):
        await self.cog.stop_player(interaction)

    @discord.ui.button(label="🔀 Shuffle", style=discord.ButtonStyle.secondary, custom_id="lyra:shuffle")
    async def shuffle(self, interaction: discord.Interaction, button: Button):
        await self.cog.shuffle_queue(interaction)



class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue = []
        self.current_track = None
        self.voice_client = None
        self.dashboard_message = None
        self.dashboard_channel = None
        self.loop_mode = 0 # 0=Off, 1=Track, 2=Queue
        self.start_time = 0
        self.manual_skip = False

    async def cog_load(self):
        self.bot.add_view(DashboardView(self))

    @commands.Cog.listener()
    async def on_ready(self):
        await self.setup_dashboard()

    async def setup_dashboard(self):
        await self.bot.wait_until_ready()
        self.dashboard_channel = self.bot.get_channel(config.MUSIC_CHANNEL_ID)
        
        if not self.dashboard_channel:
            print(f"❌ ERROR: Dashboard channel ID {config.MUSIC_CHANNEL_ID} not found! Check permissions or ID.")
            try:
                self.dashboard_channel = await self.bot.fetch_channel(config.MUSIC_CHANNEL_ID)
            except Exception as e:
                print(f"🚨 CRITICAL ERROR: Could not fetch channel: {e}")
                return

        # Find existing dashboard message
        async for message in self.dashboard_channel.history(limit=10):
            if message.author == self.bot.user:
                self.dashboard_message = message
                break
        
        if not self.dashboard_message:
            try:
                embed = self.create_dashboard_embed()
                self.dashboard_message = await self.dashboard_channel.send(embed=embed, view=DashboardView(self))
            except Exception as e:
                print(f"❌ ERROR: Could not send message: {e}")
        else:
            # Refresh view
            await self.update_dashboard()

    def create_dashboard_embed(self):
        embed = discord.Embed(title="Lyra Player 🎵", color=config.COLOR_MAIN)
        
        if self.current_track:
            status = "Now Playing ▶️"
            if self.voice_client and self.voice_client.is_paused():
                status = "Paused ⏸️"
            
            # Combine info into one main block for symmetry
            # description = f"**{self.current_track.title}**\n*{self.current_track.uploader}*\n`⏱️ {self.current_track.formatted_duration}`"
            # embed.add_field(name=status, value=description, inline=False)
            
            requester = self.current_track.requester.mention if self.current_track.requester else "Unknown"
            
            # Title and Artist
            description = f"**{self.current_track.title}**\n*{self.current_track.uploader}*"
            embed.add_field(name=status, value=description, inline=False)
            
            # Inline fields for Duration and Requester
            embed.add_field(name="Duration", value=self.current_track.formatted_duration, inline=True)
            embed.add_field(name="Requested by", value=requester, inline=True)
            
            if self.current_track.thumbnail:
                embed.set_thumbnail(url=self.current_track.thumbnail)
        else:
            embed.description = "No track playing. Paste a link to start!"
            embed.add_field(name="Status", value="Idle", inline=False)

        if self.queue:
            # Calculate total queue duration
            total_seconds = sum(int(t.duration) for t in self.queue if t.duration)
            m, s = divmod(total_seconds, 60)
            h, m = divmod(m, 60)
            if h > 0:
                total_duration = f"{h}h {m}m"
            else:
                total_duration = f"{m}m {s}s"

            queue_list = []
            for i, t in enumerate(self.queue[:10]):
                req = t.requester.mention if t.requester else "Unknown"
                title = t.title
                if len(title) > 30:
                    title = title[:27] + "..."
                queue_list.append(f"`{i+1}.` **{title}** ({t.formatted_duration}) • {req}")
            
            up_next = "\n".join(queue_list)
            if len(self.queue) > 10:
                up_next += f"\n\n**+ {len(self.queue)-10} more tracks in queue...**"
            

            embed.add_field(name=f"Up Next (Total: {total_duration})", value=up_next, inline=False)
            
            # Footer info (Total Queue Duration only)
            # embed.set_footer(text=f"Total Queue Duration: {total_duration}")
        
        return embed

    async def update_dashboard(self):
        if self.dashboard_message:
            try:
                embed = self.create_dashboard_embed()
                view = DashboardView(self)
                


                await self.dashboard_message.edit(embed=embed, view=view)
            except Exception as e:
                print(f"⚠️ ERROR in update_dashboard: {e}")

    async def send_notification(self, text, color=config.COLOR_MAIN, delete_after=10):
        if self.dashboard_channel:
            try:
                embed = discord.Embed(description=text, color=color)
                await self.dashboard_channel.send(embed=embed, delete_after=delete_after)
            except Exception as e:
                print(f"⚠️ Error sending notification: {e}")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        
        if message.channel.id != config.MUSIC_CHANNEL_ID:
            return

        # Delete user message
        try:
            await message.delete()
        except Exception as e:
            print(f"⚠️ ERROR: Could not delete message: {e}")

        if not message.author.voice:
            msg = await message.channel.send(f"{message.author.mention}, please join a voice channel first!", delete_after=5)
            return

        url = message.content.strip()
        # Basic URL validation
        if not (url.startswith("http://") or url.startswith("https://")):
            msg = await message.channel.send(f"{message.author.mention}, Lyra only accepts links here.", delete_after=5)
            return

        # Resolve URL (Spotify -> Search Query)
        query = resolve_spotify_url(url)
        
        # Join voice if not connected
        if not self.voice_client or not self.voice_client.is_connected():
            self.voice_client = await message.author.voice.channel.connect()

        # Add to queue
        search_msg = await message.channel.send(f"🔎 **Searching for:** `{query}`...")
        
        try:
            sources = await YTDLSource.create_source(query, loop=self.bot.loop, requester=message.author)
            self.queue.extend(sources)
            
            # Delete search message when found
            try: await search_msg.delete()
            except: pass

            if not self.voice_client.is_playing():
                self.play_next()
            else:
                print(f"📚 Added to queue: {sources[0].title} (Queue size: {len(self.queue)})")
                await self.update_dashboard()
        except Exception as e:
            traceback.print_exc()
            try: await search_msg.delete()
            except: pass

            error_msg = str(e)
            if "DRM protection" in error_msg:
                embed = discord.Embed(
                    title="❌ Contenido Protegido (DRM)",
                    description="Esta canción o video tiene protección de derechos de autor y no se puede reproducir.\n\n**Solución:** Intenta buscar una versión alternativa (ej. 'Lyrics' o 'Audio').",
                    color=config.COLOR_ERROR
                )
                await message.channel.send(embed=embed, delete_after=15)
            else:
                await message.channel.send(f"Error processing request: {str(e)}", delete_after=10)

    def play_next(self):
        print("🐛 Checking queue...")
        
        # Loop Track Logic
        if self.loop_mode == 1 and self.current_track:
            # Handled in after_play
            pass 

        if self.queue:
            # Get next track
            next_track = self.queue.pop(0)
            
            # Check if it's a LazySource and resolve it
            # We need to do this asynchronously, but play_next is sync (called by after callback).
            # So we create a task to resolve and play.
            if hasattr(next_track, 'get_source'): # It's a LazySource
                asyncio.run_coroutine_threadsafe(self.resolve_and_play(next_track), self.bot.loop)
                return
            
            self.current_track = next_track
            self._play_track(self.current_track)
        else:
            print("⏹️ Queue finished. Starting auto-disconnect timer (3m).")
            self.current_track = None
            asyncio.run_coroutine_threadsafe(self.update_dashboard(), self.bot.loop)
            asyncio.run_coroutine_threadsafe(self.start_disconnect_timer(), self.bot.loop)

    async def start_disconnect_timer(self):
        await asyncio.sleep(180) # 3 minutes
        if self.voice_client and not self.voice_client.is_playing() and not self.queue:
            await self.voice_client.disconnect()
            self.voice_client = None
            print("👋 Disconnected due to inactivity.")
            await self.send_notification("👋 Left the voice channel due to inactivity.", color=config.COLOR_ERROR)
            await self.update_dashboard()

    async def resolve_and_play(self, lazy_source):
        try:
            # Resolve LazySource to YTDLSource (returns a list, take first)
            sources = await lazy_source.get_source(self.bot.loop)
            if sources:
                self.current_track = sources[0]
                self._play_track(self.current_track)
            else:
                print("⚠️ Error: Resolved source is empty")
                self.play_next()
        except Exception as e:
            print(f"❌ Error resolving track: {e}")
            traceback.print_exc()
            self.play_next()

    def _play_track(self, track):
        self.manual_skip = False
        print(f"▶️ Now Playing: {track.title} ({track.formatted_duration}) | 👤 {track.requester.name}")
        try:
            self.voice_client.play(track, after=self.after_play)
            self.start_time = time.time()
            print("🎵 Audio stream started")
        except Exception as e:
            print(f"❌ ERROR in voice_client.play: {e}")
            traceback.print_exc()
            self.play_next() # Skip if error
        
        asyncio.run_coroutine_threadsafe(self.update_dashboard(), self.bot.loop)

    def after_play(self, error):
        if error:
            print(f"❌ ERROR in after_play: {error}")
        else:
            elapsed = time.time() - self.start_time
            if elapsed < 10 and not self.manual_skip:
                print(f"⚠️ Track finished too quickly ({int(elapsed)}s). Possible playback error or region lock.")
                asyncio.run_coroutine_threadsafe(
                    self.send_notification(f"⚠️ **Error:** Track finished too quickly ({int(elapsed)}s). It might be region-locked.", color=config.COLOR_ERROR),
                    self.bot.loop
                )
            else:
                print("✅ Track finished")
        
        # Handle Loop
        if self.loop_mode == 1 and self.current_track: # Loop Track
            coro = self.requeue_current()
            asyncio.run_coroutine_threadsafe(coro, self.bot.loop)
            return
        elif self.loop_mode == 2 and self.current_track: # Loop Queue
            coro = self.requeue_current(front=False)
            asyncio.run_coroutine_threadsafe(coro, self.bot.loop)
            return

        self.play_next()

    async def requeue_current(self, front=True):
        if not self.current_track:
            self.play_next()
            return
            
        try:
            # Re-create source from webpage_url (most reliable)
            url = self.current_track.webpage_url or self.current_track.url
            # We use create_source which returns a list
            sources = await YTDLSource.create_source(url, loop=self.bot.loop, requester=self.current_track.requester, is_playlist_entry=True)
            
            if sources:
                source = sources[0]
                if front:
                    self.queue.insert(0, source)
                else:
                    self.queue.append(source)
            
            self.play_next()
        except Exception as e:
            print(f"⚠️ Error requeueing: {e}")
            self.play_next()

    # --- Button Actions ---
    async def toggle_pause(self, interaction):
        try:
            if not self.voice_client:
                return await interaction.response.defer()
            
            if self.voice_client.is_paused():
                self.voice_client.resume()
                await interaction.response.defer()
            elif self.voice_client.is_playing():
                self.voice_client.pause()
                await interaction.response.defer()
            else:
                await interaction.response.defer()
            
            await self.update_dashboard()
        except Exception as e:
            print(f"❌ ERROR in toggle_pause: {e}")
            traceback.print_exc()

    async def skip_track(self, interaction):
        try:
            if not self.voice_client or not self.voice_client.is_playing():
                return await interaction.response.defer()
            self.manual_skip = True
            self.voice_client.stop() # This triggers after_play -> play_next
            await interaction.response.defer()
        except Exception as e:
            print(f"❌ ERROR in skip_track: {e}")
            traceback.print_exc()

    async def stop_player(self, interaction):
        try:
            self.queue.clear()
            if self.voice_client:
                self.manual_skip = True
                self.voice_client.stop()
                # Do not disconnect, just stop playing
            self.current_track = None
            await self.update_dashboard()
            await interaction.response.defer()
        except Exception as e:
            print(f"❌ ERROR in stop_player: {e}")
            traceback.print_exc()

    async def shuffle_queue(self, interaction):
        try:
            import random
            if len(self.queue) < 1:
                return await interaction.response.defer()
            
            random.shuffle(self.queue)
            await self.update_dashboard()
            await interaction.response.defer()
        except Exception as e:
            print(f"❌ ERROR in shuffle_queue: {e}")
            traceback.print_exc()



async def setup(bot):
    await bot.add_cog(MusicCog(bot))
