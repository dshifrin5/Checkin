import subprocess
import time
import requests
import re
import os

# === CONFIG ===
HTML_PATH = os.path.expanduser(r"C:\Users\19179\Desktop\Checkin\mobile_checkin_server.py")
GIT_BRANCH = "main"
RENDER_SERVICE_ID = "srv-d17puvgdl3ps7391mnpg"
RENDER_API_KEY = "rnd_PVTkldXhRNq8DwWypV9FzBihMVjd"
PORT = 5001

def start_ngrok():
    subprocess.run(["taskkill", "/f", "/im", "ngrok.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ngrok_proc = subprocess.Popen(["ngrok", "http", str(PORT)], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    time.sleep(5)
    try:
        response = requests.get("http://localhost:4040/api/tunnels")
        public_url = response.json()["tunnels"][0]["public_url"]
        print(f"[+] Ngrok URL: {public_url}")
        return ngrok_proc, public_url
    except Exception as e:
        print("[!] Failed to retrieve ngrok URL:", e)
        return None, None

def update_index_html(public_url):
    with open(HTML_PATH, "r", encoding="utf-8") as file:
        html = file.read()
    updated = re.sub(r"https?://[a-z0-9\-]+\.ngrok-free\.app|https://0b3a-47-18-38-63.ngrok-free.app", public_url, html)
    if html != updated:
        with open(HTML_PATH, "w", encoding="utf-8") as file:
            file.write(updated)
        print("[+] index.html updated with new ngrok URL")
        return True
    else:
        print("[~] No changes needed — URL already current.")
        return False

def commit_and_push_changes():
    subprocess.run(["git", "add", "-f", HTML_PATH], check=True)

    subprocess.run(["git", "commit", "-m", "Auto-update ngrok URL"], check=False)
    subprocess.run(["git", "push", "--set-upstream", "origin", GIT_BRANCH], check=False)
    print("[+] Pushed to GitHub")

def trigger_render_deploy():
    if not RENDER_SERVICE_ID or not RENDER_API_KEY or "<REPLACE" in RENDER_SERVICE_ID:
        print("[~] Skipping Render trigger. Update RENDER_SERVICE_ID and RENDER_API_KEY.")
        return

    headers = {
        "Authorization": f"Bearer {RENDER_API_KEY}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    response = requests.post(
        f"https://api.render.com/v1/services/{RENDER_SERVICE_ID}/deploys",
        headers=headers
    )
    if response.status_code == 201:
        print("[🚀] Render deployment triggered successfully.")
    else:
        print(f"[!] Failed to trigger deployment: {response.text}")

def auto_deploy():
    ngrok_proc, new_url = start_ngrok()
    if not new_url:
        print("[!] Failed to start ngrok. Aborting.")
        return
    changed = update_index_html(new_url)
    if changed:
        commit_and_push_changes()
    else:
        print("[~] Skipped commit and push.")
    trigger_render_deploy()
    print("[⚠️] Ngrok will now remain running. Do NOT terminate this script.")
    print("[🌐] Public URL:", new_url)
    return ngrok_proc

if __name__ == "__main__":
    try:
        ngrok_proc = auto_deploy()
    except Exception as e:
        print("[Auto Deploy Failed]", e)

    # === Run your Flask app ===
    import VoiceServerTest  # This will run your real app on port 5001
