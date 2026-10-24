# ⚡ OtakuVault — Modern Anime & Manga Tracker

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.x-000000?style=for-the-badge&logo=flask&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-3-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![AniList API](https://img.shields.io/badge/AniList-GraphQL-02A9FF?style=for-the-badge&logo=anilist&logoColor=white)
![Gemini AI](https://img.shields.io/badge/Google_Gemini-2.5_Flash-8E75C2?style=for-the-badge&logo=google&logoColor=white)

**OtakuVault** is a modern, responsive web application for anime and manga enthusiasts to track their watch and read progress, discover where to stream titles, curate a Hall of Fame of characters, and get AI-powered recommendations.

---

## ✨ Features

- 📺 **Anime & Manga Library**:
  - Track watch and read progress with sleek visual progress bars.
  - **Quick `+1` Increment Button**: One-click progress updates without page reloads.
  - **Live In-Library Search & Sorting**: Instant real-time filtering by title, rating, or progress.
  - **Status Management**: Filter by Watching/Reading, Completed, Plan to Watch/Read, On Hold, or Dropped.

- 🍿 **Where to Watch (AniList Streaming Integration)**:
  - Live metadata fetched via **AniList GraphQL API**.
  - Direct links to official streaming platforms (**Crunchyroll**, **Netflix**, **Hulu**, **Amazon Prime Video**, **YouTube**, **Bilibili**, **Tubi**, etc.).
  - Direct AniList page links and official YouTube trailer previews.

- 👑 **Hall of Fame & Character Autocomplete**:
  - Curate your favorite anime and manga series.
  - **Live AniList Character Search**: As you type a character's name (e.g., Zoro, Gojo, Makima), instant suggestions appear with thumbnails.
  - **1-Click Autofill**: Automatically populates character portrait, name, and origin anime/manga.

- 🤖 **OtakuSensei AI Companion**:
  - Powered by **Google Gemini 2.5 Flash**.
  - Has personalized context of your top-rated titles and favorites to give custom recommendations, watch order guides, and spoiler-free advice.

- 💡 **Discovery & Exploration**:
  - Live trending anime and manga feeds from AniList.
  - Quick-import any trending title straight into your vault with a single click.

- 📱 **Modern Glassmorphic Dark UI**:
  - Premium cyber-dark aesthetic with neon crimson/purple accents.
  - Fully responsive across desktop, tablet, and mobile with a slide-out drawer menu.

---

## 🚀 Quickstart Guide

### 1. Clone the Repository
```bash
git clone https://github.com/Neel1005-blip/AnimeDB.git
cd AnimeDB
```

### 2. Set Up a Virtual Environment (Optional but Recommended)
```bash
python -m venv venv
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables (Optional)
For the **OtakuSensei AI Companion**, obtain a free Gemini API key from [Google AI Studio](https://aistudio.google.com/) and set:
```bash
# Windows PowerShell:
$env:GEMINI_API_KEY="your-gemini-api-key"

# Windows Command Prompt:
set GEMINI_API_KEY="your-gemini-api-key"

# Linux/macOS:
export GEMINI_API_KEY="your-gemini-api-key"
```

### 5. Launch the Application
```bash
python app.py
```
Open your browser and navigate to:
```
http://127.0.0.1:5000
```

---

## 📁 Project Structure

```
AnimeDB/
├── app.py                 # Flask server, database models, AniList & Gemini routes
├── anime_tracker.db       # SQLite local database
├── requirements.txt       # Python package dependencies
├── README.md              # Project documentation
├── static/
│   ├── style.css          # Unified glassmorphic dark design system
│   └── script.js          # Interactive UI, AniList details modal, real-time search
└── templates/
    ├── index.html         # Anime library dashboard & quick stats
    ├── manga.html         # Manga library dashboard & quick stats
    ├── favorites.html     # Hall of fame & live character autocomplete
    ├── suggestions.html   # Discovery & trending AniList explorer
    ├── chat.html          # OtakuSensei AI chat assistant
    ├── login.html         # User sign-in
    └── signup.html        # Account registration
```

---

## 📜 License
This project is open source and available under the [MIT License](LICENSE).
