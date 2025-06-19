from flask import Flask, request, jsonify
import tempfile, os, re, time, cv2, pytesseract, pyautogui, numpy as np
from PyPDF2 import PdfReader
from difflib import SequenceMatcher
import soundfile as sf
import mss
import traceback
import easyocr
import threading
import queue
reader = easyocr.Reader(['en'], gpu=True)
from flask_cors import CORS
from openai import OpenAI
from werkzeug.utils import secure_filename
from openpyxl import Workbook, load_workbook
checkin_queue = queue.Queue()

client = OpenAI(api_key="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"
)  # Replace with your actual key

reader = easyocr.Reader(['en'], gpu=True)
app = Flask(__name__)
CORS(app)
last_matched = {}
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
PDF_PATH = "list.pdf"

def normalize_name(name):
    return re.sub(r'\s+', ' ', name.strip().lower())

def move_and_right_click(x, y, offset_x, offset_y):
    screen_x = x + offset_x
    screen_y = y + offset_y
    pyautogui.moveTo(screen_x, screen_y, duration=0.3)
    pyautogui.rightClick()
    print(f"[ACTION] Right-clicked at ({screen_x}, {screen_y})")
    time.sleep(0.2)

    pyautogui.press('s')
    time.sleep(0.2)
    pyautogui.press('h')
    time.sleep(0.2)

    pyautogui.moveTo(screen_x, 0, duration=0.2)
    pyautogui.keyDown('alt')
    pyautogui.press('f')
    pyautogui.keyUp('alt')
    time.sleep(0.2)
    pyautogui.press('f')
    time.sleep(0.2)
    pyautogui.press('n')
    print("[ACTION] Finished key sequence")

def extract_name_position(img, target_name):
    target_clean = re.sub(r'[^a-zA-Z ]', '', target_name).lower()
    best_score = 0
    best_position = None
    best_text = ""

    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    results = reader.readtext(img_rgb)

    texts = [(bbox, text, conf) for (bbox, text, conf) in results]
    target_parts = target_clean.split()
    if len(target_parts) != 2:
        return None, None
    first_name, last_name = target_parts

    for i in range(len(texts)):
        bbox1, text1, conf1 = texts[i]
        text1_clean = re.sub(r'[^a-zA-Z ]', '', text1).lower()

        if last_name in text1_clean:
            for j in range(len(texts)):
                if i == j:
                    continue
                bbox2, text2, conf2 = texts[j]
                text2_clean = re.sub(r'[^a-zA-Z ]', '', text2).lower()
                score = SequenceMatcher(None, text2_clean, first_name).ratio()
                prefix = first_name.startswith(text2_clean[:3]) or text2_clean.startswith(first_name[:3])
                if score > 0.6 or prefix:
                    # Use average of all 8 points (4 from each box)
                    all_x = [pt[0] for pt in bbox1 + bbox2]
                    all_y = [pt[1] for pt in bbox1 + bbox2]
                    cx = sum(all_x) // len(all_x)
                    cy = sum(all_y) // len(all_y)

                    score_total = (score + 1.0) / 2
                    if score_total > best_score:
                        best_score = score_total
                        best_text = f"{text1} {text2}"
                        best_position = (cx, cy)

    # Fallback: check for full name in a single box
    for (bbox, text, conf) in results:
        text_clean = re.sub(r'[^a-zA-Z ]', '', text).strip().lower()
        score = SequenceMatcher(None, text_clean, target_clean).ratio()
        if score > best_score:
            xs = [pt[0] for pt in bbox]
            ys = [pt[1] for pt in bbox]
            cx = sum(xs) // len(xs)
            cy = sum(ys) // len(ys)
            best_score = score
            best_text = text
            best_position = (cx, cy)

    if best_score > 0.5:
        print(f"[EASYOCR MATCH] '{best_text}' (Score: {int(best_score * 100)}%) @ {best_position}")
        return best_position, best_text

    print(f"[EASYOCR WARN] '{target_name}' not found.")
    return None, None


def extract_appointments_from_screen():
    img, _, _ = capture_monitor()
    text = pytesseract.image_to_string(img)
    appointments = []
    for line in text.splitlines():
        match = re.search(r"(\d{1,2}:\d{2} (?:AM|PM)).*?([A-Z][a-z]+(?:,| [A-Z])[a-z]+)", line)
        if match:
            time_str, name = match.groups()
            appointments.append({
                "name": name.strip(),
                "time": time_str.strip()
            })
    return appointments



from datetime import datetime, timedelta

def find_family_group(matched_name, all_names):
    matched_last = matched_name.split(",")[0].rstrip("a").lower()
    family = []
    for name in all_names:
        if name == matched_name:
            continue  # Skip matched name itself
        last = name.split(",")[0].rstrip("a").lower()
        if last == matched_last:
            family.append(name)
    return [matched_name] + sorted(family)  # Ensure matched person is first




def extract_names_and_providers_from_pdf(pdf_path):
    reader = PdfReader(pdf_path)
    name_provider_list = []

    for page in reader.pages:
        text = page.extract_text()
        if not text:
            continue

        for line in text.split('\n'):
            line = line.strip()

            # Skip known headers or empty lines
            if not line or "APPOINTMENT LIST" in line or "DATE TIME" in line:
                continue

            # Detect provider code pattern at end
            match = re.search(r'/OP\d{2}', line)
            if match:
                slash_index = match.start()

                if slash_index >= 4:
                    provider_prefix = line[slash_index - 4:slash_index]
                    provider = f"{provider_prefix}/OP{line[slash_index + 3:slash_index + 5]}"
                    line_before_provider = line[:slash_index - 4].strip()
                else:
                    provider = ''
                    line_before_provider = line

                # Strip time/date prefix: "05/22 2:00Pm"
                name_match = re.search(r'^\d{2}/\d{2}\s+\d{1,2}:\d{2}[aApP][mM]\s+(.*)', line_before_provider)
                if name_match:
                    raw_name = name_match.group(1)
                else:
                    raw_name = line_before_provider  # fallback

                # Remove garbage prefixes like "Firm" or "??????"
                raw_name = re.sub(r'^(Firm|[?]{2,}|Con |C/Upd |Lmm |Seat |Txcomp )\s*', '', raw_name, flags=re.IGNORECASE)


                # Normalize spacing and capitalization
                name = re.sub(r'\s+', ' ', raw_name.title().replace(" ,", ",")).strip()

                name_provider_list.append((name, provider))
                print(f"[DEBUG] Found: Name='{name}', Provider='{provider}'")

    print(f"[DEBUG] Total extracted name-provider pairs: {len(name_provider_list)}")
    return name_provider_list



def capture_monitor(monitor_number=2):
    with mss.mss() as sct:
        monitors = sct.monitors
        if monitor_number >= len(monitors):
            return None
        monitor = monitors[monitor_number]
        screenshot = sct.grab(monitor)
        img = np.array(screenshot)
        return img, monitor["left"], monitor["top"]

def transcribe_with_whisper_api(audio_path):
    with open(audio_path, "rb") as f:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            response_format="verbose_json",
            language="en"
        )
    segments = transcript.segments or []
    combined = " ".join(s.text for s in segments if hasattr(s, "text"))
    return combined.strip()

def find_best_match(spoken, candidates):
    spoken_clean = re.sub(r'[^a-zA-Z ]', '', spoken).lower().strip()
    if len(spoken_clean.split()) < 1:
        return None, 0.0
    best_score = 0
    best_name = None
    for name in candidates:
        parts = name.replace(',', '').split()
        variants = [
            name.lower(),
            ' '.join(reversed(parts)),
            ' '.join(parts),
            parts[0],
            parts[-1]
        ]
        for variant in variants:
            score = SequenceMatcher(None, spoken_clean, variant.lower()).ratio()
            if score > best_score:
                best_score = score
                best_name = name
    print(f"🤖 Matched '{spoken}' → '{best_name}' (Score: {int(best_score * 100)}%)")
    return best_name if best_score >= 0.49 else None, best_score

def checkin_worker():
    while True:
        names, result_queue = checkin_queue.get()
        try:
            with app.app_context():  # 👈 Fix: create app context
                response = perform_checkin_for_names(names)
                result_queue.put(response)
        except Exception as e:
            import traceback
            traceback.print_exc()
            with app.app_context():
                result_queue.put(jsonify({"status": "error", "message": str(e)}))
        checkin_queue.task_done()



@app.route("/voice-match", methods=["POST"])
def voice_match():
    global last_matched
    try:
        if not os.path.exists(PDF_PATH):
            return jsonify({"error": "No PDF uploaded yet"}), 400

       # print("[DEBUG] Extracting names and providers from PDF...")
        name_provider_pairs = extract_names_and_providers_from_pdf(PDF_PATH)
        names = [pair[0] for pair in name_provider_pairs]
        provider_map = dict(name_provider_pairs)

       # print(f"[DEBUG] Loaded {len(names)} names.")
        print(f"[DEBUG] Provider map sample: {list(provider_map.items())[:5]}")

        if request.is_json and "typed_name" in request.json:
            typed_name = request.json["typed_name"].strip()
        #    print(f"[DEBUG] Received typed name: {typed_name}")
            match, score = find_best_match(typed_name, names)
        elif "audio" in request.files:
            audio = request.files["audio"]
            audio_path = "voice.wav"
            audio.save(audio_path)
         #   print(f"[DEBUG] Saved audio file, transcribing...")
            transcription = transcribe_with_whisper_api(audio_path)
            typed_name = transcription
            print(f"[DEBUG] Transcription: {typed_name}")
            match, score = find_best_match(transcription, names)
        else:
            return jsonify({"error": "No valid input provided"}), 400

        if not match:
            print("[DEBUG] No match found.")
            return jsonify({"match": None, "status": "no match"})

     #   print(f"[DEBUG] Best match: {match} with score {score:.2f}")
        last_matched = {
            "pdf_name": match,
            "typed_name": typed_name,
        }

        family_matches = find_family_group(match, names)
        normalized_provider_map = {normalize_name(k): v for k, v in provider_map.items()}
        family_with_providers = family_matches  # 👈 List of strings only

        print(f"[DEBUG] Family group: {family_with_providers}")

        matched_provider = normalized_provider_map.get(normalize_name(match), "")

        provider_code = matched_provider.split("/")[0] if "/" in matched_provider else matched_provider
        is_restricted = provider_code in ("IPAY", "PVT1")
        is_prop_flag = (provider_code == "PROP")
        print(f"[DEBUG] Matched provider: {matched_provider} | Prefix: {provider_code} | Restricted: {is_restricted}")


        return jsonify({
            "match": match,
            "transcription": typed_name,
            "family_matches": family_with_providers,
            "provider": matched_provider,
            "flag_restricted": is_restricted,
            "flag_prop": is_prop_flag,
            "status": "match returned"
        })


    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/mobile-checkin", methods=["POST"])
def mobile_checkin():
    try:
        data = request.get_json()
        typed_name = data.get("name", "").strip()
        if not typed_name:
            return jsonify({"status": "error", "message": "Name is required"}), 400

        name_provider_pairs = extract_names_and_providers_from_pdf(PDF_PATH)
        names = [pair[0] for pair in name_provider_pairs]
        provider_map = dict(name_provider_pairs)

        # Use fuzzy matching (same as /voice-match)
        match, score = find_best_match(typed_name, names)
        if not match:
            return jsonify({"status": "no_match", "message": "Name not found"})

        normalized_provider_map = {normalize_name(k): v for k, v in provider_map.items()}
        matched_provider = normalized_provider_map.get(normalize_name(match), "")
        provider_code = matched_provider.split("/")[0] if "/" in matched_provider else matched_provider

        # Handle restricted types
        if provider_code in ("IPAY", "PVT1"):
            return jsonify({
                "status": "restricted",
                "message": "Please see the front desk regarding payment."
            })
        elif provider_code == "PROP":
            return jsonify({
                "status": "restricted",
                "message": "Please use the QR code below to fill out the New Patient Form."
            })

        # Include family group matches
        family_matches = find_family_group(match, names)

        return jsonify({
            "status": "match",
            "name": match,
            "family_matches": family_matches
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500




@app.route("/mobile-confirm", methods=["POST"])
def mobile_confirm():
    try:
        data = request.get_json()
        names = data.get("names", [])
        if not names:
            return jsonify({"status": "error", "message": "Names list is required"}), 400

        # ✅ Call confirm_name() as a regular function and pass names directly
        result_queue = queue.Queue()
        checkin_queue.put((names, result_queue))
        response = result_queue.get()  # Wait for processing
        return response


    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

def perform_checkin_for_names(names):
    try:
        if not names:
            return jsonify({"error": "No names provided"}), 400

        name_provider_pairs = extract_names_and_providers_from_pdf(PDF_PATH)
        provider_map = dict(name_provider_pairs)
        normalized_provider_map = {normalize_name(k): v for k, v in provider_map.items()}

        restricted_names = []
        allowed_names = []
        prop_names = []

        for name in names:
            provider = normalized_provider_map.get(normalize_name(name), "")
            prefix = provider.split("/")[0] if "/" in provider else provider
            if prefix in ("IPAY", "PVT1"):
                restricted_names.append(name)
            elif prefix == "PROP":
                prop_names.append(name)
            else:
                allowed_names.append(name)

        if restricted_names and not allowed_names:
            return jsonify({"status": "restricted_all_skipped", "confirmed_names": []})

        partial_flag = bool(restricted_names and allowed_names)

        for name in allowed_names:
            try:
                print(f"[PROCESSING] Attempting to check in: {name}")
                last_name = name.split(',')[0].strip()
                if last_name.endswith("a"):
                    last_name = last_name[:-1]

                result = capture_monitor()
                if result is None:
                    print(f"⚠️ Monitor not found for {name}")
                    continue
                img, offset_x, offset_y = result

                pyautogui.moveTo(1770 + offset_x, 115 + offset_y)
                pyautogui.doubleClick()
                time.sleep(0.2)
                pyautogui.typewrite(last_name)
                time.sleep(3)

                result = capture_monitor()
                if result is None:
                    print(f"⚠️ Monitor not found after typing {last_name}")
                    continue
                img, offset_x, offset_y = result
                img = img[125:]
                offset_y += 125

                variants = [name]
                if ',' in name:
                    parts = name.split(', ')
                    variants += [f"{parts[1]} {parts[0]}", parts[0]]

                matched = False
                for v in variants:
                    pos, best_text = extract_name_position(img, v)
                    if pos:
                        print(f"✅ Found: {v} as '{best_text}' at {pos}")
                        move_and_right_click(*pos, offset_x, offset_y)
                        matched = True
                        break

                if not matched:
                    print(f"❌ No OCR match for {name}")

                time.sleep(6)

            except Exception as e:
                print(f"❌ Error processing {name}: {e}")
                continue

        status = "partial" if partial_flag else "confirmed"
        return jsonify({
            "status": status,
            "confirmed_names": allowed_names
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/confirm-name", methods=["POST"])
def confirm_name():
    try:
        names = request.json.get("names", [])
        if not names:
            return jsonify({"error": "No names provided"}), 400

        # ✅ Route the kiosk check-in request into the global queue
        result_queue = queue.Queue()
        checkin_queue.put((names, result_queue))
        response = result_queue.get()  # Wait for processing result
        return response

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500



if __name__ == "__main__":
    threading.Thread(target=checkin_worker, daemon=True).start()
    app.run(host="0.0.0.0", port=5001)
    
