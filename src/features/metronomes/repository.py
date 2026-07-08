import json

from features.shared.paths import DB_FILE, OUT_DIR
from features.shared.utils import sanitize_filename


def load_db():
        OUT_DIR.mkdir(parents=True, exist_ok=True)

        if not DB_FILE.exists():
                return []

        try:
                with DB_FILE.open("r", encoding="utf-8") as f:
                        data = json.load(f)

                if isinstance(data, list):
                        return data

                return []
        except Exception:
                return []


def save_db(entries):
        OUT_DIR.mkdir(parents=True, exist_ok=True)

        with DB_FILE.open("w", encoding="utf-8") as f:
                json.dump(entries, f, indent=2, ensure_ascii=False)


def load_entries_from_files():
        OUT_DIR.mkdir(parents=True, exist_ok=True)

        db_entries = load_db()
        entries_by_filename = {
                entry.get("filename"): entry
                for entry in db_entries
                if isinstance(entry, dict) and entry.get("filename")
        }

        entries = []

        for path in sorted(OUT_DIR.iterdir(), key=lambda p: p.name.lower()):
                if not path.is_file() or path.suffix.lower() != ".wav":
                        continue

                entry = dict(entries_by_filename.get(path.name, {}))
                entry["filename"] = path.name
                entry.setdefault("created_at", path.stat().st_mtime)
                entries.append(entry)

        return entries


def unique_path(filename):
        filename = sanitize_filename(filename)
        path = OUT_DIR / filename

        if not path.exists():
                return path

        stem = path.stem
        suffix = path.suffix

        n = 2
        while True:
                candidate = OUT_DIR / f"{stem}_{n}{suffix}"
                if not candidate.exists():
                        return candidate
                n += 1


def default_filename_from_bpm(bpm):
        OUT_DIR.mkdir(parents=True, exist_ok=True)

        n = 1
        while True:
                filename = f"bpm-{n:03d}.wav"
                if not (OUT_DIR / filename).exists():
                        return filename
                n += 1
