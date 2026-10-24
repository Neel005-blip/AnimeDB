import json
import os
import sqlite3
import ssl
import urllib.parse
import urllib.request
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from dotenv import load_dotenv
load_dotenv()  # <-- Add this here on line 10
import os
try:
    from google import genai
except ImportError:
    genai = None

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "otakuvault-secret-key-3021")

DB_NAME = "anime_tracker.db"

# Initialize Google GenAI Client
gemini_api_key = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=gemini_api_key) if (gemini_api_key and genai) else None


def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def fetch_mal_metadata(title, medium="anime"):
    """Fetches high-res cover image URL and total episode/chapter count using Jikan (MyAnimeList API)."""
    endpoint = "manga" if str(medium).lower() == "manga" else "anime"
    encoded_title = urllib.parse.quote(title.strip())
    url = f"https://api.jikan.moe/v4/{endpoint}?q={encoded_title}&limit=1"

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json",
        },
    )

    try:
        context = ssl._create_unverified_context()
        with urllib.request.urlopen(req, context=context, timeout=6) as response:
            data = json.loads(response.read().decode("utf-8"))
            results = data.get("data", [])
            if results:
                first_match = results[0]
                images = first_match.get("images", {})
                jpg_images = images.get("jpg", {})
                webp_images = images.get("webp", {})

                cover = (
                    jpg_images.get("large_image_url")
                    or webp_images.get("large_image_url")
                    or jpg_images.get("image_url")
                )

                total = (
                    first_match.get("chapters")
                    if endpoint == "manga"
                    else first_match.get("episodes")
                )

                return cover, (total or 0)
    except Exception as e:
        print(f"[MAL Fetch Error] Failed for '{title}': {e}")

    return None, 0


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    """)

    # Media entries table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            medium TEXT NOT NULL DEFAULT 'anime',
            status TEXT NOT NULL DEFAULT 'Watching',
            progress INTEGER DEFAULT 0,
            total INTEGER DEFAULT 0,
            score INTEGER DEFAULT 0,
            image_url TEXT,
            is_favorite INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    # Automatic schema migrations for existing databases
    cursor.execute("PRAGMA table_info(entries)")
    existing_columns = [col[1] for col in cursor.fetchall()]

    if "medium" not in existing_columns:
        cursor.execute("ALTER TABLE entries ADD COLUMN medium TEXT DEFAULT 'anime'")
    if "is_favorite" not in existing_columns:
        cursor.execute("ALTER TABLE entries ADD COLUMN is_favorite INTEGER DEFAULT 0")
    if "image_url" not in existing_columns:
        cursor.execute("ALTER TABLE entries ADD COLUMN image_url TEXT")

    # Favorite characters table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS favorite_characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            char_name TEXT NOT NULL,
            anime_origin TEXT,
            image_url TEXT,
            notes TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    cursor.execute("UPDATE entries SET medium = LOWER(medium) WHERE medium IS NOT NULL")
    conn.commit()
    conn.close()


init_db()


@app.context_processor
def inject_user():
    return dict(username=session.get("username", "Otaku"))


# ---------------------- AUTHENTICATION ----------------------

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            return render_template("signup.html", error="Username and password are required.")

        conn = get_db_connection()
        user = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()

        if user:
            conn.close()
            return render_template("signup.html", error="Username already exists.")

        hashed_pw = generate_password_hash(password)
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, hashed_pw)
        )
        conn.commit()
        conn.close()
        return redirect(url_for("login"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(url_for("index"))

        return render_template("login.html", error="Invalid username or password.")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------------- LIBRARY VIEWS ----------------------

@app.route("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("login"))

    status_filter = request.args.get("status", "all")
    conn = get_db_connection()

    all_entries = conn.execute(
        "SELECT * FROM entries WHERE user_id = ? AND LOWER(medium) = 'anime' ORDER BY id DESC",
        (session["user_id"],)
    ).fetchall()
    conn.close()

    if status_filter == "all":
        entries = all_entries
    else:
        entries = [e for e in all_entries if (e["status"] or "").lower() == status_filter.lower()]

    total_count = len(all_entries)
    total_episodes = sum(e["progress"] or 0 for e in all_entries)
    rated = [e["score"] for e in all_entries if e["score"] and e["score"] > 0]
    mean_score = round(sum(rated) / len(rated), 1) if rated else 0.0

    status_counts = {
        "all": total_count,
        "Watching": sum(1 for e in all_entries if (e["status"] or "").lower() == "watching"),
        "Completed": sum(1 for e in all_entries if (e["status"] or "").lower() == "completed"),
        "Plan to Watch": sum(1 for e in all_entries if (e["status"] or "").lower() == "plan to watch"),
        "On Hold": sum(1 for e in all_entries if (e["status"] or "").lower() == "on hold"),
        "Dropped": sum(1 for e in all_entries if (e["status"] or "").lower() == "dropped"),
    }

    stats = {
        "total": total_count,
        "episodes": total_episodes,
        "mean_score": mean_score,
        "completed": status_counts["Completed"],
        "counts": status_counts
    }

    return render_template("index.html", entries=entries, current_filter=status_filter, stats=stats)


@app.route("/manga")
def manga():
    if "user_id" not in session:
        return redirect(url_for("login"))

    status_filter = request.args.get("status", "all")
    conn = get_db_connection()

    all_entries = conn.execute(
        "SELECT * FROM entries WHERE user_id = ? AND LOWER(medium) = 'manga' ORDER BY id DESC",
        (session["user_id"],)
    ).fetchall()
    conn.close()

    if status_filter == "all":
        entries = all_entries
    else:
        entries = [e for e in all_entries if (e["status"] or "").lower() == status_filter.lower()]

    total_count = len(all_entries)
    total_chapters = sum(e["progress"] or 0 for e in all_entries)
    rated = [e["score"] for e in all_entries if e["score"] and e["score"] > 0]
    mean_score = round(sum(rated) / len(rated), 1) if rated else 0.0

    status_counts = {
        "all": total_count,
        "Reading": sum(1 for e in all_entries if (e["status"] or "").lower() == "reading"),
        "Completed": sum(1 for e in all_entries if (e["status"] or "").lower() == "completed"),
        "Plan to Read": sum(1 for e in all_entries if (e["status"] or "").lower() == "plan to read"),
        "On Hold": sum(1 for e in all_entries if (e["status"] or "").lower() == "on hold"),
        "Dropped": sum(1 for e in all_entries if (e["status"] or "").lower() == "dropped"),
    }

    stats = {
        "total": total_count,
        "chapters": total_chapters,
        "mean_score": mean_score,
        "completed": status_counts["Completed"],
        "counts": status_counts
    }

    return render_template("manga.html", entries=entries, current_filter=status_filter, stats=stats)


# ---------------------- ENTRY MANAGEMENT ----------------------

@app.route("/add_entry", methods=["POST"])
def add_entry():
    if "user_id" not in session:
        return redirect(url_for("login"))

    title = request.form.get("title", "").strip()
    medium = request.form.get("medium", "anime").lower().strip()
    default_status = "Reading" if medium == "manga" else "Watching"
    status = request.form.get("status", default_status).strip()
    progress = int(request.form.get("progress", 0) or 0)
    total = int(request.form.get("total", 0) or 0)
    score = int(request.form.get("score", 0) or 0)
    image_url = request.form.get("image_url", "").strip() or None

    if title:
        # Fallback to Jikan/MAL metadata if image or total count was left empty
        if not image_url or total == 0:
            auto_cover, auto_total = fetch_mal_metadata(title, medium)
            if not image_url and auto_cover:
                image_url = auto_cover
            if total == 0 and auto_total:
                total = auto_total

        conn = get_db_connection()
        conn.execute("""
            INSERT INTO entries (user_id, title, medium, status, progress, total, score, image_url, is_favorite)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
        """, (session["user_id"], title, medium, status, progress, total, score, image_url))
        conn.commit()
        conn.close()

    return redirect(url_for("manga" if medium == "manga" else "index"))


@app.route("/api/increment_progress/<int:entry_id>", methods=["POST"])
def increment_progress(entry_id):
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_db_connection()
    entry = conn.execute(
        "SELECT id, progress, total, status, medium FROM entries WHERE id = ? AND user_id = ?",
        (entry_id, session["user_id"])
    ).fetchone()

    if not entry:
        conn.close()
        return jsonify({"error": "Entry not found"}), 404

    current_prog = entry["progress"] or 0
    total = entry["total"] or 0
    new_prog = current_prog + 1
    new_status = entry["status"]

    if total > 0 and new_prog >= total:
        new_prog = total
        new_status = "Completed"

    conn.execute(
        "UPDATE entries SET progress = ?, status = ? WHERE id = ? AND user_id = ?",
        (new_prog, new_status, entry_id, session["user_id"])
    )
    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "progress": new_prog,
        "total": total,
        "status": new_status,
        "medium": entry["medium"]
    })


@app.route("/update_entry/<int:entry_id>", methods=["POST"])
def update_entry(entry_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    progress = int(request.form.get("progress", 0) or 0)
    total = int(request.form.get("total", 0) or 0)
    score = int(request.form.get("score", 0) or 0)
    status = request.form.get("status", "Watching").strip()

    conn = get_db_connection()
    entry = conn.execute(
        "SELECT medium FROM entries WHERE id = ? AND user_id = ?",
        (entry_id, session["user_id"])
    ).fetchone()

    if entry:
        conn.execute("""
            UPDATE entries SET progress = ?, total = ?, score = ?, status = ?
            WHERE id = ? AND user_id = ?
        """, (progress, total, score, status, entry_id, session["user_id"]))
        conn.commit()
        medium = (entry["medium"] or "anime").lower()
    else:
        medium = "anime"

    conn.close()
    return redirect(url_for("manga" if medium == "manga" else "index"))


@app.route("/delete_entry/<int:entry_id>", methods=["POST"])
def delete_entry(entry_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    entry = conn.execute(
        "SELECT medium FROM entries WHERE id = ? AND user_id = ?",
        (entry_id, session["user_id"])
    ).fetchone()

    if entry:
        conn.execute(
            "DELETE FROM entries WHERE id = ? AND user_id = ?",
            (entry_id, session["user_id"])
        )
        conn.commit()
        medium = entry["medium"]
    else:
        medium = "anime"

    conn.close()
    return redirect(url_for("manga" if medium == "manga" else "index"))


# ---------------------- FAVORITES FEATURE ----------------------

@app.route("/favorites")
def favorites():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    conn = get_db_connection()

    fav_media = conn.execute(
        "SELECT * FROM entries WHERE user_id = ? AND is_favorite = 1 ORDER BY title ASC",
        (user_id,)
    ).fetchall()

    fav_chars = conn.execute(
        "SELECT * FROM favorite_characters WHERE user_id = ? ORDER BY id DESC",
        (user_id,)
    ).fetchall()

    conn.close()
    return render_template("favorites.html", media=fav_media, characters=fav_chars)


@app.route("/toggle_favorite/<int:entry_id>", methods=["POST"])
def toggle_favorite(entry_id):
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_db_connection()
    entry = conn.execute(
        "SELECT is_favorite FROM entries WHERE id = ? AND user_id = ?",
        (entry_id, session["user_id"])
    ).fetchone()

    if entry:
        new_status = 0 if entry["is_favorite"] == 1 else 1
        conn.execute(
            "UPDATE entries SET is_favorite = ? WHERE id = ? AND user_id = ?",
            (new_status, entry_id, session["user_id"])
        )
        conn.commit()
        conn.close()
        return jsonify({"success": True, "is_favorite": new_status})

    conn.close()
    return jsonify({"error": "Entry not found"}), 404


@app.route("/add_character", methods=["POST"])
def add_character():
    if "user_id" not in session:
        return redirect(url_for("login"))

    name = request.form.get("char_name", "").strip()
    origin = request.form.get("anime_origin", "").strip()
    image_url = request.form.get("image_url", "").strip() or None
    notes = request.form.get("notes", "").strip()

    if name:
        conn = get_db_connection()
        conn.execute("""
            INSERT INTO favorite_characters (user_id, char_name, anime_origin, image_url, notes)
            VALUES (?, ?, ?, ?, ?)
        """, (session["user_id"], name, origin, image_url, notes))
        conn.commit()
        conn.close()

    return redirect(url_for("favorites"))


@app.route("/delete_character/<int:char_id>", methods=["POST"])
def delete_character(char_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    conn.execute(
        "DELETE FROM favorite_characters WHERE id = ? AND user_id = ?",
        (char_id, session["user_id"])
    )
    conn.commit()
    conn.close()

    return redirect(url_for("favorites"))


# ---------------------- LIVE MODAL AUTOCOMPLETE SEARCH ----------------------

@app.route("/api/search_anime")
def search_anime():
    if "user_id" not in session:
        return jsonify([])

    query = request.args.get("q", "").strip()
    medium = request.args.get("medium", "anime").lower().strip()

    if len(query) < 2:
        return jsonify([])

    media_type = "MANGA" if medium == "manga" else "ANIME"

    gql_query = """
    query ($search: String, $type: MediaType) {
      Page(page: 1, perPage: 6) {
        media(search: $search, type: $type, sort: SEARCH_MATCH) {
          id
          title {
            english
            romaji
          }
          coverImage {
            large
          }
          episodes
          chapters
        }
      }
    }
    """
    payload = json.dumps({
        "query": gql_query,
        "variables": {"search": query, "type": media_type}
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://graphql.anilist.co",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
    )

    try:
        context = ssl._create_unverified_context()
        with urllib.request.urlopen(req, context=context, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            items = data.get("data", {}).get("Page", {}).get("media", [])
            results = []
            for item in items:
                title = item.get("title", {}).get("english") or item.get("title", {}).get("romaji")
                cover = item.get("coverImage", {}).get("large") or ""
                total = item.get("chapters") if media_type == "MANGA" else item.get("episodes")
                results.append({
                    "title": title,
                    "cover": cover,
                    "total": total or 0
                })
            return jsonify(results)
    except Exception as e:
        print(f"[Search Autocomplete Error]: {e}")
        return jsonify([])


# ---------------------- CHARACTER AUTOCOMPLETE SEARCH ----------------------

@app.route("/api/search_character")
def search_character():
    if "user_id" not in session:
        return jsonify([])

    query = request.args.get("q", "").strip()
    if len(query) < 2:
        return jsonify([])

    gql_query = """
    query ($search: String) {
      Page(page: 1, perPage: 8) {
        characters(search: $search, sort: SEARCH_MATCH) {
          id
          name {
            full
            native
            userPreferred
          }
          image {
            large
            medium
          }
          media(sort: POPULARITY_DESC, perPage: 1) {
            nodes {
              id
              title {
                english
                romaji
              }
            }
          }
        }
      }
    }
    """
    payload = json.dumps({
        "query": gql_query,
        "variables": {"search": query}
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://graphql.anilist.co",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
    )

    try:
        context = ssl._create_unverified_context()
        with urllib.request.urlopen(req, context=context, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            items = data.get("data", {}).get("Page", {}).get("characters", [])
            results = []
            for item in items:
                name_obj = item.get("name", {}) or {}
                name = name_obj.get("userPreferred") or name_obj.get("full") or ""
                img = (item.get("image", {}) or {}).get("large") or (item.get("image", {}) or {}).get("medium") or ""
                media_nodes = (item.get("media", {}) or {}).get("nodes", [])
                origin = ""
                if media_nodes:
                    origin = media_nodes[0].get("title", {}).get("english") or media_nodes[0].get("title", {}).get("romaji") or ""
                results.append({
                    "name": name,
                    "image": img,
                    "origin": origin
                })
            return jsonify(results)
    except Exception as e:
        print(f"[Search Character Error]: {e}")
        return jsonify([])


# ---------------------- ANIME DETAILS & WHERE TO WATCH ----------------------

@app.route("/api/anime_details")
def anime_details():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    title = request.args.get("title", "").strip()
    medium = request.args.get("medium", "anime").lower().strip()

    if not title:
        return jsonify({"error": "Title is required"}), 400

    media_type = "MANGA" if medium == "manga" else "ANIME"

    gql_query = """
    query ($search: String, $type: MediaType) {
      Media(search: $search, type: $type) {
        id
        siteUrl
        title {
          english
          romaji
          native
        }
        bannerImage
        coverImage {
          large
          extraLarge
        }
        format
        status
        episodes
        chapters
        duration
        genres
        averageScore
        description(asHtml: false)
        studios(isMain: true) {
          nodes {
            name
          }
        }
        trailer {
          id
          site
        }
        externalLinks {
          id
          url
          site
          type
          color
        }
      }
    }
    """

    payload = json.dumps({
        "query": gql_query,
        "variables": {"search": title, "type": media_type}
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://graphql.anilist.co",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
    )

    try:
        context = ssl._create_unverified_context()
        with urllib.request.urlopen(req, context=context, timeout=7) as response:
            data = json.loads(response.read().decode("utf-8"))
            media_data = data.get("data", {}).get("Media")
            if not media_data:
                return jsonify({"error": "No details found on AniList"}), 404

            ext_links = media_data.get("externalLinks", []) or []
            streaming_links = []
            other_links = []

            for link in ext_links:
                site_name = link.get("site") or "Official Platform"
                link_url = link.get("url")
                link_color = link.get("color")
                link_type = link.get("type")

                if not link_url:
                    continue

                item = {
                    "site": site_name,
                    "url": link_url,
                    "color": link_color or "#ff3366",
                    "type": link_type
                }

                if link_type == "STREAMING":
                    streaming_links.append(item)
                else:
                    other_links.append(item)

            site_url = media_data.get("siteUrl") or f"https://anilist.co/anime/{media_data.get('id', '')}"

            studios_list = [s.get("name") for s in media_data.get("studios", {}).get("nodes", []) if s.get("name")]

            trailer = media_data.get("trailer")
            trailer_url = None
            if trailer and trailer.get("site") == "youtube" and trailer.get("id"):
                trailer_url = f"https://www.youtube.com/watch?v={trailer['id']}"

            title_obj = media_data.get("title", {}) or {}
            clean_title = title_obj.get("english") or title_obj.get("romaji") or title

            images = media_data.get("coverImage", {}) or {}
            cover_img = images.get("extraLarge") or images.get("large") or ""

            score = media_data.get("averageScore")
            score_out = round(score / 10, 1) if score else None

            desc = media_data.get("description") or "No synopsis available."
            desc = desc.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")

            return jsonify({
                "success": True,
                "data": {
                    "id": media_data.get("id"),
                    "title": clean_title,
                    "romaji": title_obj.get("romaji"),
                    "siteUrl": site_url,
                    "cover": cover_img,
                    "banner": media_data.get("bannerImage"),
                    "format": media_data.get("format"),
                    "status": media_data.get("status"),
                    "episodes": media_data.get("episodes"),
                    "chapters": media_data.get("chapters"),
                    "duration": media_data.get("duration"),
                    "score": score_out,
                    "genres": media_data.get("genres", []),
                    "studios": studios_list,
                    "description": desc,
                    "trailerUrl": trailer_url,
                    "streamingLinks": streaming_links,
                    "otherLinks": other_links
                }
            })
    except Exception as e:
        print(f"[AniList Details API Error]: {e}")
        return jsonify({"error": f"Failed to fetch details: {str(e)}"}), 500


# ---------------------- DISCOVERY & SUGGESTIONS SEARCH ----------------------

@app.route("/api/discover")
def api_discover():
    if "user_id" not in session:
        return jsonify([])

    query = request.args.get("q", "").strip()
    medium = request.args.get("medium", "anime").lower().strip()
    media_type = "MANGA" if medium == "manga" else "ANIME"

    if query:
        gql_query = """
        query ($search: String, $type: MediaType) {
          Page(page: 1, perPage: 12) {
            media(search: $search, type: $type, sort: POPULARITY_DESC) {
              id
              title {
                english
                romaji
              }
              coverImage {
                large
              }
              episodes
              chapters
              averageScore
              genres
              description(asHtml: false)
            }
          }
        }
        """
        variables = {"search": query, "type": media_type}
    else:
        gql_query = """
        query ($type: MediaType) {
          Page(page: 1, perPage: 12) {
            media(type: $type, sort: TRENDING_DESC) {
              id
              title {
                english
                romaji
              }
              coverImage {
                large
              }
              episodes
              chapters
              averageScore
              genres
              description(asHtml: false)
            }
          }
        }
        """
        variables = {"type": media_type}

    payload = json.dumps({"query": gql_query, "variables": variables}).encode("utf-8")
    req = urllib.request.Request(
        "https://graphql.anilist.co",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
    )

    try:
        context = ssl._create_unverified_context()
        with urllib.request.urlopen(req, context=context, timeout=6) as response:
            data = json.loads(response.read().decode("utf-8"))
            items = data.get("data", {}).get("Page", {}).get("media", [])
            results = []
            for item in items:
                title = item.get("title", {}).get("english") or item.get("title", {}).get("romaji")
                cover = item.get("coverImage", {}).get("large") or ""
                total = item.get("chapters") if media_type == "MANGA" else item.get("episodes")
                score = round((item.get("averageScore") or 0) / 10, 1)
                genres = item.get("genres", [])[:3]
                desc = item.get("description") or "No synopsis available."
                clean_desc = desc.replace("\n", " ")[:140] + "..." if len(desc) > 140 else desc

                results.append({
                    "title": title,
                    "cover": cover,
                    "total": total or 0,
                    "score": score,
                    "genres": genres,
                    "description": clean_desc,
                    "medium": medium
                })
            return jsonify(results)
    except Exception as e:
        print(f"[Discover API Error]: {e}")
        return jsonify([])


# ---------------------- SUGGESTIONS & AI CHAT ----------------------

@app.route("/suggestions")
def suggestions():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("suggestions.html")


@app.route("/chat")
def chat():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("chat.html")


@app.route("/api/ai_chat", methods=["POST"])
def ai_chat():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    user_msg = data.get("message", "").strip()

    if not user_msg:
        return jsonify({"error": "Message is required"}), 400

    if not client:
        return jsonify({
            "response": "Gemini API key is not configured. Please set GEMINI_API_KEY."
        })

    conn = get_db_connection()
    user_entries = conn.execute(
        "SELECT title, medium, score, is_favorite FROM entries WHERE user_id = ? AND (score >= 8 OR is_favorite = 1) LIMIT 10",
        (session["user_id"],)
    ).fetchall()
    conn.close()

    context_list = [f"{e['title']} ({e['medium']}, score: {e['score']})" for e in user_entries]
    favorites_context = ", ".join(context_list) if context_list else "No recorded favorites yet."

    system_instruction = (
        "You are OtakuSensei, an expert anime and manga companion assistant. "
        f"The user's favorite and top-rated titles: {favorites_context}. "
        "Keep responses energetic, accurate, helpful, and concise. Avoid spoilers."
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_msg,
            config={"system_instruction": system_instruction}
        )
        return jsonify({"response": response.text})
    except Exception as e:
        return jsonify({"response": f"AI Assistant encountered an error: {str(e)}"}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)