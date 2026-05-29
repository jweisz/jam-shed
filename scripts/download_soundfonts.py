import os
import requests
import sys

# SoundFont Sources
SOUNDFONTS = [
    {
        "url": "https://github.com/musescore/MuseScore/raw/master/share/sound/FluidR3Mono_GM.sf3",
        "filename": "FluidR3Mono_GM.sf3"
    },
    {
        "url": "https://sourceforge.net/p/mscore/code/HEAD/tree/trunk/mscore/share/sound/TimGM6mb.sf2?format=raw",
        "filename": "TimGM6mb.sf2"
    }
]

OUTPUT_DIR = "assets/soundfonts"

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

def download_file(url, dest_path):
    print(f"Downloading {os.path.basename(dest_path)} from {url}...")
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        total_size = int(response.headers.get('content-length', 0))

        with open(dest_path, 'wb') as f:
            downloaded = 0
            for data in response.iter_content(chunk_size=4096):
                size = f.write(data)
                downloaded += size
                # Simple progress bar
                if total_size > 0:
                    percent = int((downloaded / total_size) * 100)
                    sys.stdout.write(f"\rProgress: [{('=' * (percent // 5)).ljust(20)}] {percent}%")
                    sys.stdout.flush()
        print("\nDownload complete!")
    except Exception as e:
        print(f"\nError downloading {url}: {e}")

if __name__ == "__main__":
    ensure_dir(OUTPUT_DIR)

    for sf in SOUNDFONTS:
        dest = os.path.join(OUTPUT_DIR, sf["filename"])
        if os.path.exists(dest):
            print(f"SoundFont already exists at {dest}")
        else:
            download_file(sf["url"], dest)

    print(f"SoundFonts ready in: {os.path.abspath(OUTPUT_DIR)}")
