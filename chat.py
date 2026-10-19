#!/usr/bin/env python3
"""
System Scanner + Chat přes link (ntfy.sh)
Použití: python scanner.py
"""
import platform, socket, getpass, json, time, threading, uuid, re, sys
import requests

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    print("[!] psutil není nainstalován – některá data budou chybět (pip install psutil)")

NTFY_BASE = "https://ntfy.sh"


# ---------- 1) Sken systému ----------
def scan_system():
    info = {
        "hostname": socket.gethostname(),
        "user":     getpass.getuser(),
        "os":       f"{platform.system()} {platform.release()}",
        "arch":     platform.machine(),
        "python":   platform.python_version(),
        "cpu":      platform.processor() or "N/A",
        "cores":    None,
        "ram_gb":   None,
        "disk_gb":  None,
        "ip":       None,
    }
    if HAS_PSUTIL:
        info["cores"] = psutil.cpu_count(logical=True)
        info["ram_gb"] = round(psutil.virtual_memory().total / (1024 ** 3), 1)
        try:
            info["disk_gb"] = round(psutil.disk_usage("/").total / (1024 ** 3), 1)
        except Exception:
            pass
    # lokální IP (bez odesílání dat ven)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        info["ip"] = s.getsockname()[0]
        s.close()
    except Exception:
        pass
    return info


def format_info(info):
    out = ["=== SYSTEM INFO ==="]
    for k, v in info.items():
        out.append(f"  {k:10}: {v}")
    return "\n".join(out)


# ---------- 2) Chat přes ntfy.sh ----------
def safe_topic(t):
    """ntfy povoluje jen [a-z0-9_-], max 64 znaků."""
    t = re.sub(r"[^a-zA-Z0-9_-]", "-", t).strip("-").lower()
    return t[:64] or f"scan-{uuid.uuid4().hex[:8]}"


class Chat:
    def __init__(self, topic, username):
        self.topic = topic
        self.username = username
        self.url = f"{NTFY_BASE}/{topic}"
        self.last_id = None
        self.seen = set()
        self.running = True

    def send(self, text):
        payload = f"[{self.username}] {text}"
        try:
            requests.post(self.url, data=payload.encode("utf-8"), timeout=5)
        except Exception as e:
            print(f"\n! Chyba odeslání: {e}")

    def _poll_loop(self):
        first = True
        while self.running:
            try:
                params = {"poll": "1"}
                if self.last_id:
                    params["since"] = self.last_id
                elif first:
                    params["since"] = "15s"   # ať nezahltíme historii
                r = requests.get(f"{self.url}/json", params=params, timeout=10)
                first = False
                if r.status_code == 200:
                    for line in r.text.splitlines():
                        try:
                            msg = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if msg.get("event") != "message":
                            continue
                        mid = msg.get("id")
                        if mid in self.seen:
                            continue
                        self.seen.add(mid)
                        self.last_id = mid
                        body = msg.get("message", "")
                        if body.startswith(f"[{self.username}]"):
                            continue  # vlastní zprávy přeskoč
                        print(f"\n<< {body}\n> ", end="", flush=True)
            except Exception:
                pass
            time.sleep(2)

    def start(self):
        threading.Thread(target=self._poll_loop, daemon=True).start()

    def stop(self):
        self.running = False


# ---------- 3) Main ----------
def main():
    print("=== System Scanner + Chat ===")
    raw = input("Chatovací místnost / link (Enter = náhodná): ").strip()
    topic = safe_topic(raw) if raw else f"scan-{uuid.uuid4().hex[:8]}"
    username = input("Tvoje přezdívka: ").strip() or getpass.getuser()

    print(f"\n[*] Sdílený link: {NTFY_BASE}/{topic}")
    print("[*] Skenuji systém...\n")
    info = scan_system()
    print(format_info(info))

    chat = Chat(topic, username)
    chat.start()
    chat.send(f"připojen | {info['os']} | {info['hostname']}")

    print("\n[Chat] Napiš zprávu + Enter. /quit = konec.\n")
    try:
        while True:
            text = input("> ").strip()
            if text.lower() in ("/quit", "/exit"):
                break
            if text:
                chat.send(text)
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        chat.send("odpojen")
        chat.stop()
        print("\n[Chat] Ukončeno.")


if __name__ == "__main__":
    main()