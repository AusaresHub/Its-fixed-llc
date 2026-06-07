"""Fetch a business's real Google Place photos as base64 data URIs.
Reusable across the demo build. Reads GOOGLE_MAPS_API_KEY from env/.env."""
import io, base64, os, requests
from dotenv import load_dotenv
load_dotenv()
try:
    from PIL import Image
    _PIL = True
except ImportError:
    _PIL = False

KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")

def fetch_place_photos(place_id: str, n: int = 6, max_h: int = 900) -> list[str]:
    """Return up to n photos for a place as JPEG data URIs (resized)."""
    if not KEY or not place_id:
        return []
    try:
        r = requests.get(f"https://places.googleapis.com/v1/places/{place_id}",
                         headers={"X-Goog-Api-Key": KEY, "X-Goog-FieldMask": "photos"},
                         timeout=15)
        photos = r.json().get("photos", [])[:n]
    except Exception:
        return []
    out = []
    for p in photos:
        try:
            m = requests.get(f"https://places.googleapis.com/v1/{p['name']}/media",
                             params={"maxHeightPx": max_h, "key": KEY, "skipHttpRedirect": "true"},
                             timeout=15)
            url = m.json().get("photoUri")
            if not url:
                continue
            raw = requests.get(url, timeout=25).content
            if _PIL:
                im = Image.open(io.BytesIO(raw)).convert("RGB")
                im.thumbnail((1280, max_h), Image.LANCZOS)
                buf = io.BytesIO(); im.save(buf, "JPEG", quality=72, optimize=True)
                raw = buf.getvalue()
            out.append("data:image/jpeg;base64," + base64.b64encode(raw).decode())
        except Exception:
            continue
    return out

if __name__ == "__main__":
    import sys, json
    pid = sys.argv[1] if len(sys.argv) > 1 else ""
    uris = fetch_place_photos(pid, n=int(sys.argv[2]) if len(sys.argv) > 2 else 6)
    print(json.dumps({"count": len(uris), "bytes": sum(len(u) for u in uris)}))
