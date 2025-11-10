import socket
import threading
import queue
import tkinter as tk
from tkinter import ttk, messagebox
import time

# Optional: pip install msgpack for UDP MsgPack decoding
try:
    import msgpack
    HAS_MSGPACK = True
except Exception:
    HAS_MSGPACK = False

# ---- CoLa-A framing ----
STX = b"\x02"
ETX = b"\x03"

DEFAULT_SENSOR_IP = "192.168.0.1"
DEFAULT_COLA_A_PORT = 2111
DEFAULT_UDP_PORT   = 2115

# ---- Factory default hashes per access level (hidden from UI) ----
# If passwords were changed on the device, update these to the new hex hashes.
HASH_BY_LEVEL = {
    "2": "B21ACE26",  # Maintenance (view/diagnostics)
    "3": "F4724744",  # Authorized client (configure)
    "4": "81BE23AA",  # Service (advanced)
}

# ---- Telegram catalog (CoLa-A ASCII) ----
# For params in UI:
#   - plain string/int -> simple Entry
#   - dict with {"value": "...", "choices": [(label, value), ...]} -> Combobox
TELEGRAMS = {
    "login": {
        "label": "Login (choose level; hash is internal)",
        # hash will be injected internally based on selected level
        "cmd": "sMN SetAccessMode {level} {hash}",
        "params": {
            "level": {
                "value": "3",
                "choices": [
                    ("Maintenance (2)", "2"),
                    ("Authorized client (3)", "3"),
                    ("Service (4)", "4"),
                ]
            },
            # NOTE: no 'hash' param exposed here; we inject it in code.
        },
        "needs_login": False,
    },
    "read_scan_data_format": {
        "label": "Read Scan Data Format",
        "cmd": "sRN ScanDataFormat",
        "params": {},
        "needs_login": False,
    },
    "read_stream_settings": {
        "label": "Read Stream Settings",
        "cmd": "sRN ScanDataEthSettings",
        "params": {},
        "needs_login": False,
    },
    "set_stream_udp": {
        "label": "Set Stream (UDP destination)",
        "cmd": "sWN ScanDataEthSettings +{proto} +{ip1} +{ip2} +{ip3} +{ip4} +{port}",
        # proto: 1=UDP
        "params": {
            "proto": {"value": "1", "choices": [("UDP (1)", "1")]},
            "ip1":   "192",
            "ip2":   "168",
            "ip3":   "0",
            "ip4":   "100",  # <- set to your PC's IP
            "port":  str(DEFAULT_UDP_PORT),
        },
        "needs_login": True,
    },
    "enable_streaming": {
        "label": "Enable Streaming",
        "cmd": "sWN ScanDataEnable {onoff}",
        "params": {"onoff": {"value": "1", "choices": [("On (1)", "1"), ("Off (0)", "0")]}},
        "needs_login": True,
    },
    "disable_streaming": {
        "label": "Disable Streaming",
        "cmd": "sWN ScanDataEnable 0",
        "params": {},
        "needs_login": True,
    },
    "start_measurement": {
        "label": "Start Measurement",
        "cmd": "sMN LMCstartmeas",
        "params": {},
        "needs_login": True,
    },
    "stop_measurement": {
        "label": "Stop Measurement",
        "cmd": "sMN LMCstopmeas",
        "params": {},
        "needs_login": True,
    },
    "read_serial_number": {
        "label": "Read Serial Number",
        "cmd": "sRN SerialNumber",
        "params": {},
        "needs_login": False,
    },
    "save_to_eeprom": {
        "label": "Save Parameters (EEPROM)",
        "cmd": "sMN mEEwriteall",
        "params": {},
        "needs_login": True,
    },
}

# ---- I/O helpers ----

def cola_a_once(host: str, port: int, ascii_cmd: str, timeout=2.5) -> bytes:
    """Send one CoLa-A ASCII telegram and return raw reply bytes."""
    payload = STX + ascii_cmd.encode("ascii") + ETX
    with socket.create_connection((host, port), timeout=timeout) as s:
        s.sendall(payload)
        return s.recv(16384)

def hex_bytes(b: bytes) -> str:
    return " ".join(f"{x:02X}" for x in b)

def bytes_to_readable_ascii(b: bytes) -> str:
    """Printable ASCII with non-printables shown as '.'; STX/ETX stripped."""
    core = b.replace(STX, b"").replace(ETX, b"")
    out = []
    for x in core:
        if 32 <= x < 127 or x in (9, 10, 13):
            out.append(chr(x))
        else:
            out.append(".")
    return "".join(out)

def parse_cola_ascii_line(ascii_payload: str):
    """
    Light CoLa-A reply parser:
      sAN ...  -> answer to sMN
      sRA ...  -> answer to sRN
      sWA ...  -> answer to sWN (write answer)
      sFA ...  -> failure
    Returns dict with type, command, args.
    """
    s = ascii_payload.replace("\x02", "").replace("\x03", "").strip()
    if not s:
        return {"type": "empty", "command": "", "args": []}
    tokens = s.split()
    t0 = tokens[0] if tokens else ""
    cmd = tokens[1] if len(tokens) > 1 else ""
    args = tokens[2:] if len(tokens) > 2 else []

    # convert +nnn to ints
    conv = []
    for a in args:
        if a.startswith("+") and a[1:].isdigit():
            conv.append(int(a[1:]))
        else:
            conv.append(a)
    return {"type": t0, "command": cmd, "args": conv}

# ---- UDP listener ----

class UDPListener(threading.Thread):
    def __init__(self, ip: str, port: int, out_q: queue.Queue, try_msgpack: bool):
        super().__init__(daemon=True)
        self.ip = ip
        self.port = port
        self.out_q = out_q
        self.try_msgpack = try_msgpack and HAS_MSGPACK
        self._stop = threading.Event()
        self.sock = None

    def run(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.bind((self.ip, self.port))
            self.sock.settimeout(0.5)
            self.out_q.put(f"[UDP] Listening on {self.ip}:{self.port}")
        except Exception as e:
            self.out_q.put(f"[UDP] ERROR binding: {e}")
            return

        while not self._stop.is_set():
            try:
                data, addr = self.sock.recvfrom(65535)
            except socket.timeout:
                continue
            except Exception as e:
                self.out_q.put(f"[UDP] Socket error: {e}")
                break

            if not data:
                continue

            if self.try_msgpack:
                try:
                    msg = msgpack.unpackb(data, raw=False)
                    if isinstance(msg, dict):
                        keys = list(msg.keys())[:12]
                        self.out_q.put(f"[UDP] {len(data)} bytes from {addr} | msgpack keys: {keys}")
                    else:
                        self.out_q.put(f"[UDP] {len(data)} bytes from {addr} | msgpack type: {type(msg).__name__}")
                except Exception as e:
                    self.out_q.put(f"[UDP] {len(data)} bytes from {addr} | msgpack decode failed: {e}")
            else:
                self.out_q.put(f"[UDP HEX] {hex_bytes(data)}")
                self.out_q.put(f"[UDP TXT] {bytes_to_readable_ascii(data)}")

        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass
        self.out_q.put("[UDP] Listener stopped.")

    def stop(self):
        self._stop.set()

# ---- Tk App ----

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SICK multiScan – CoLa-A Toolkit")
        self.minsize(960, 640)

        self.out_q = queue.Queue()
        self.udp_thread = None

        # maps for combobox (label -> value)
        self._param_choice_maps = {}
        # hold Tk variables for parameters
        self.param_entries = {}

        self._build_ui()
        self.after(80, self._drain_out_q)

    def _build_ui(self):
        # -- Top bar --
        top = ttk.Frame(self, padding=8)
        top.pack(fill="x")

        ttk.Label(top, text="Sensor IP:").grid(row=0, column=0, sticky="w")
        self.ip_var = tk.StringVar(value=DEFAULT_SENSOR_IP)
        ttk.Entry(top, textvariable=self.ip_var, width=16).grid(row=0, column=1, padx=(4, 10))

        ttk.Label(top, text="CoLa-A TCP Port:").grid(row=0, column=2, sticky="w")
        self.port_var = tk.StringVar(value=str(DEFAULT_COLA_A_PORT))
        ttk.Entry(top, textvariable=self.port_var, width=8).grid(row=0, column=3, padx=(4, 10))

        ttk.Label(top, text="UDP Listen Port:").grid(row=0, column=4, sticky="w")
        self.udp_port_var = tk.StringVar(value=str(DEFAULT_UDP_PORT))
        ttk.Entry(top, textvariable=self.udp_port_var, width=8).grid(row=0, column=5, padx=(4, 10))

        self.msgpack_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text="Try MsgPack decode", variable=self.msgpack_var).grid(row=0, column=6, padx=(0, 8))

        self.udp_btn = ttk.Button(top, text="Start UDP Listener", command=self._toggle_udp)
        self.udp_btn.grid(row=0, column=7, padx=(4, 0))

        self.clear_btn = ttk.Button(top, text="Clear Log", command=self._clear_log)
        self.clear_btn.grid(row=0, column=8, padx=(8, 0))

        # -- Telegram selection --
        mid = ttk.Frame(self, padding=8)
        mid.pack(fill="x")

        ttk.Label(mid, text="Telegram:").grid(row=0, column=0, sticky="w")
        self.tele_keys = list(TELEGRAMS.keys())
        self.tele_var = tk.StringVar(value=self.tele_keys[0])
        self.tele_combo = ttk.Combobox(mid, textvariable=self.tele_var,
                                       values=self.tele_keys, state="readonly", width=34)
        self.tele_combo.grid(row=0, column=1, sticky="w", padx=(6, 12))
        self.tele_combo.bind("<<ComboboxSelected>>", self._on_tele_changed)

        ttk.Label(mid, text="Description:").grid(row=0, column=2, sticky="w")
        self.desc_lbl = ttk.Label(mid, text=TELEGRAMS[self.tele_keys[0]]["label"])
        self.desc_lbl.grid(row=0, column=3, sticky="w")

        # -- Params frame --
        self.param_frame = ttk.LabelFrame(self, text="Parameters", padding=8)
        self.param_frame.pack(fill="x", padx=8, pady=(0, 4))
        self._rebuild_param_entries(self.tele_keys[0])

        # -- Command builder + send --
        cmd_frame = ttk.Frame(self, padding=8)
        cmd_frame.pack(fill="x")

        self.cmd_var = tk.StringVar()
        ttk.Label(cmd_frame, text="Command Preview:").pack(anchor="w")
        self.cmd_entry = ttk.Entry(cmd_frame, textvariable=self.cmd_var)
        self.cmd_entry.pack(fill="x", pady=2)

        self.send_btn = ttk.Button(cmd_frame, text="Send Telegram", command=self._send_telegram)
        self.send_btn.pack(anchor="e", pady=(4, 2))

        # -- Output --
        out_frame = ttk.Frame(self, padding=8)
        out_frame.pack(fill="both", expand=True)

        ttk.Label(out_frame, text="Log:").pack(anchor="w")
        self.out_text = tk.Text(out_frame, height=20)
        self.out_text.pack(fill="both", expand=True)
        self.out_text.configure(state="disabled")

        # initial preview
        self._update_cmd_preview()

    # ---- Parameter UI ----

    def _on_tele_changed(self, *_):
        key = self.tele_var.get()
        self.desc_lbl.config(text=TELEGRAMS[key]["label"])
        self._rebuild_param_entries(key)
        self._update_cmd_preview()

    def _rebuild_param_entries(self, key: str):
        for w in self.param_frame.winfo_children():
            w.destroy()
        self.param_entries.clear()
        self._param_choice_maps.clear()

        params_meta = TELEGRAMS[key]["params"]
        if not params_meta:
            ttk.Label(self.param_frame, text="(No parameters)").grid(row=0, column=0, sticky="w")
            return

        row = 0
        for pname, meta in params_meta.items():
            ttk.Label(self.param_frame, text=pname + ":").grid(row=row, column=0, sticky="w")

            if isinstance(meta, dict) and "choices" in meta:
                choices = meta["choices"]
                label_to_value = {label: value for (label, value) in choices}
                self._param_choice_maps[pname] = label_to_value

                default_val = meta.get("value", "")
                default_label = None
                for label, val in choices:
                    if val == default_val:
                        default_label = label
                        break
                if default_label is None and choices:
                    default_label = choices[0][0]

                var = tk.StringVar(value=default_label)
                self.param_entries[pname] = var
                cb = ttk.Combobox(self.param_frame, textvariable=var, state="readonly",
                                  values=[label for (label, _) in choices], width=32)
                cb.grid(row=row, column=1, padx=6, pady=2, sticky="w")
                cb.bind("<<ComboboxSelected>>", lambda _e: self._update_cmd_preview())
            else:
                default_str = meta.get("value") if isinstance(meta, dict) else meta
                var = tk.StringVar(value=str(default_str) if default_str is not None else "")
                self.param_entries[pname] = var
                ent = ttk.Entry(self.param_frame, textvariable=var, width=32)
                ent.grid(row=row, column=1, padx=6, pady=2, sticky="w")
                ent.bind("<KeyRelease>", lambda _e: self._update_cmd_preview())

            row += 1

    def _build_cmd(self) -> str:
        key = self.tele_var.get()
        tmpl = TELEGRAMS[key]["cmd"]
        resolved = {}
        params_meta = TELEGRAMS[key]["params"]

        for pname, meta in params_meta.items():
            if isinstance(meta, dict) and "choices" in meta:
                label = self.param_entries[pname].get()
                val = self._param_choice_maps.get(pname, {}).get(label, label)
                resolved[pname] = val
            else:
                resolved[pname] = self.param_entries[pname].get()

        # Inject hidden hash for login
        if key == "login":
            level = resolved.get("level", "3")
            hash_hex = HASH_BY_LEVEL.get(level)
            if not hash_hex:
                raise ValueError(f"No hash configured for level {level}. Update HASH_BY_LEVEL.")
            resolved["hash"] = hash_hex

        try:
            return tmpl.format(**resolved) if resolved else tmpl
        except KeyError:
            return tmpl

    def _update_cmd_preview(self, *_):
        self.cmd_var.set(self._build_cmd())

    # ---- Send / UDP / Log ----

    def _send_telegram(self):
        host = self.ip_var.get().strip()
        try:
            port = int(self.port_var.get().strip())
        except ValueError:
            messagebox.showerror("Error", "Invalid TCP port")
            return

        cmd = self._build_cmd()
        self._log(f">> {cmd}")
        t = threading.Thread(target=self._send_thread, args=(host, port, cmd), daemon=True)
        t.start()

    def _send_thread(self, host, port, cmd):
        try:
            reply = cola_a_once(host, port, cmd, timeout=3.0)

            # Show ascii, hex, readable
            ascii_part = reply.replace(STX, b"").replace(ETX, b"")
            try:
                ascii_str = ascii_part.decode("ascii", errors="replace")
            except Exception:
                ascii_str = str(ascii_part)

            self.out_q.put(f"<< (ascii) {ascii_str}")
            self.out_q.put(f"<< (hex)   {hex_bytes(reply)}")
            self.out_q.put(f"<< (readable) {bytes_to_readable_ascii(reply)}")

            # Parsed summary
            parsed = parse_cola_ascii_line(ascii_str)
            if parsed["type"] != "empty":
                self.out_q.put("<< (parsed) type: {t}, command: {c}, args: {a}".format(
                    t=parsed["type"], c=parsed["command"], a=parsed["args"]
                ))

                # For ScanDataEthSettings-like replies, summarize ip:port if present
                if parsed["command"].lower().startswith("scandataethsettings") and parsed["args"]:
                    nums = [a for a in parsed["args"] if isinstance(a, int)]
                    if len(nums) >= 5:
                        ip = ".".join(map(str, nums[:4]))
                        port_num = nums[4]
                        self.out_q.put(f"<< (parsed) stream dest -> {ip}:{port_num}")

        except Exception as e:
            self.out_q.put(f"<< ERROR: {e}")

    def _toggle_udp(self):
        if self.udp_thread and self.udp_thread.is_alive():
            self.udp_thread.stop()
            self.udp_thread = None
            self.udp_btn.config(text="Start UDP Listener")
            return

        try:
            port = int(self.udp_port_var.get().strip())
        except ValueError:
            messagebox.showerror("Error", "Invalid UDP port")
            return

        try_msgpack = bool(self.msgpack_var.get())
        if try_msgpack and not HAS_MSGPACK:
            messagebox.showwarning("MsgPack", "msgpack package not installed; decoding will be skipped.")
            try_msgpack = False

        self.udp_thread = UDPListener("0.0.0.0", port, self.out_q, try_msgpack=try_msgpack)
        self.udp_thread.start()
        self.udp_btn.config(text="Stop UDP Listener")

    def _clear_log(self):
        self.out_text.configure(state="normal")
        self.out_text.delete("1.0", "end")
        self.out_text.configure(state="disabled")

    def _log(self, text: str):
        self.out_q.put(text)

    def _drain_out_q(self):
        try:
            while True:
                line = self.out_q.get_nowait()
                self.out_text.configure(state="normal")
                self.out_text.insert("end", line + "\n")
                self.out_text.see("end")
                self.out_text.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(80, self._drain_out_q)

    def on_close(self):
        try:
            if self.udp_thread and self.udp_thread.is_alive():
                self.udp_thread.stop()
                time.sleep(0.2)
        except Exception:
            pass
        self.destroy()

if __name__ == "__main__":
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()