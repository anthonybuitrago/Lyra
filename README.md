# 🎵 Lyra Music Bot

Lyra is a lightweight, high-performance Discord Music Bot built with `discord.py` and `yt-dlp`. It features a modern, interactive dashboard UI for controlling playback without typing commands.

## ✨ Features

- **Interactive Dashboard:** Control music with buttons (Play/Pause, Skip, Stop, Shuffle) and see the queue in real-time.
- **YouTube & Spotify Support:** Plays music from YouTube links and searches. Automatically resolves Spotify links to YouTube tracks.
- **Smart Queue:** Manage your playlist with an easy-to-read queue display.
- **Robust Error Handling:** Detects playback errors and region locks automatically.
- **Cookies Support:** Uses `cookies.txt` to bypass YouTube's "Sign In" restrictions and age-gated content.

## 🛠️ Prerequisites

- **Python 3.8+**
- **FFmpeg** (Must be installed and added to your system PATH)
- **Discord Bot Token**

## 📥 Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/anthonybuitrago/Lyra.git
    cd Lyra
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Setup FFmpeg:**
    Ensure `ffmpeg` is installed and accessible from your terminal. You can check this by running `ffmpeg -version`.

## ⚙️ Configuration

1.  **Environment Variables:**
    Create a `.env` file in the root directory and add your Discord Bot Token:
    ```env
    DISCORD_TOKEN=your_token_here
    ```

2.  **Bot Configuration:**
    Edit `config.py` to set your preferences:
    - `MUSIC_CHANNEL_ID`: The ID of the text channel where the bot will listen for links and show the dashboard.
    - `COLOR_MAIN`: The hex color for the bot's embeds.

3.  **YouTube Cookies (Critical):**
    To avoid YouTube blocking the bot (HTTP 429 or "Sign In" errors), you must provide a `cookies.txt` file.
    - Use a browser extension like "Get cookies.txt LOCALLY" to export cookies from YouTube while logged in.
    - Save the file as `cookies.txt` in the root directory of the project.
    - **Note:** Do NOT commit this file to GitHub! It is already added to `.gitignore`.

## 🚀 Usage

1.  **Start the bot:**
    ```bash
    python lyra.py
    ```

2.  **Play Music:**
    - Go to the configured **Music Channel**.
    - Simply paste a **YouTube** or **Spotify** link.
    - The bot will join your voice channel and start playing.

3.  **Controls:**
    Use the buttons on the dashboard message to control playback:
    - ⏯️ **Resume/Pause**
    - ⏭️ **Skip**
    - ⏹️ **Stop**
    - 🔀 **Shuffle**

## 📝 License

This project is open-source and available under the MIT License.
