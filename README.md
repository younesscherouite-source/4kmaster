# VDROP — 4K Video Downloader

A full-stack video downloader with a dark industrial UI powered by Flask + yt-dlp.

---

## 📁 Project Structure

```
video-downloader/
├── app.py                        # Flask entry point
├── requirements.txt
├── downloads/                    # Saved video files (auto-created)
├── backend/
│   ├── database/
│   │   └── db.py                 # SQLite init & connection
│   ├── models/
│   │   └── video.py              # CRUD operations for videos table
│   ├── routes/
│   │   └── api.py                # REST API endpoints
│   └── services/
│       └── downloader.py         # yt-dlp wrapper + threading
└── frontend/
    ├── index.html
    ├── style.css
    └── script.js
```

---

## ⚙️ Setup

### 1. Prerequisites
- Python 3.10+
- `ffmpeg` installed and on your PATH (required by yt-dlp for merging audio+video)

**Install ffmpeg:**
```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg

# Windows
# Download from https://ffmpeg.org/download.html and add to PATH
```

### 2. Create a virtual environment
```bash
cd video-downloader
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the app
```bash
python app.py
```

Open your browser at **http://localhost:5000**

---

## 🔌 REST API

| Method | Endpoint           | Description                         |
|--------|--------------------|-------------------------------------|
| POST   | `/api/download`    | Start a download                    |
| GET    | `/api/videos`      | List all downloads (history)        |
| GET    | `/api/videos/<id>` | Poll a single download for progress |

### POST `/api/download`
```json
// Request body
{ "url": "https://www.youtube.com/watch?v=...", "quality": "1080p" }

// Response 202
{ "id": 1, "message": "Download started!" }
```

### GET `/api/videos`
```json
[
  {
    "id": 1,
    "url": "https://...",
    "title": "Video Title",
    "quality": "1080p",
    "status": "done",
    "progress": 100,
    "file_size": "245.3 MB",
    "created_at": "2024-01-15 10:30:00"
  }
]
```

---

## 🎯 Supported Qualities

| Label | Resolution |
|-------|-----------|
| 4K    | Up to 2160p |
| 1080p | Full HD |
| 720p  | HD |
| 480p  | SD |
| BEST  | Best available |

---

## 📌 Notes

- Videos are saved to the `downloads/` folder relative to the project root.
- The SQLite database (`backend/database/videos.db`) is created automatically.
- Downloads run in background daemon threads — the server stays responsive.
- The frontend auto-refreshes download history every 5 seconds.
- yt-dlp supports 1000+ sites including YouTube, Vimeo, Twitter, TikTok, Instagram, and more.
