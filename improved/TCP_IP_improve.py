import socket
import threading
import queue
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
from datetime import datetime

# === Constants ===
STX = b'\x02'
ETX = b'\x03'
BUFFER_SIZE = 4096

DEFAULT_IP = "192.168.0.1"
DEFAULT_PORT = 2111
DEFAULT_MESSAGE = "sRN LMDscandata"
DEFAULT_TIMEOUT = 5.0  # seconds (internal only)


class TCPClientApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("TCP Client (STX/ETX)")
        self.minsize(640, 400)

        pad = 10
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ==== Styles ====
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        elif "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("TButton", padding=(10, 6))
        style.configure("Status.TLabel", foreground="#666")
        style.configure("Header.TLabelframe.Label", font=("", 10, "bold"))

        # ==== Connection Frame ====
        conn = ttk.LabelFrame(self, text="Connection", style="Header.TLabelframe")
        conn.grid(row=0, column=0, sticky="ew", padx=pad, pady=(pad, 5))
        conn.grid_columnconfigure(1, weight=1)
        conn.grid_columnconfigure(3, weight=1)

        ttk.Label(conn, text="IP Address").grid(row=0, column=0, sticky="e", padx=(pad, 5), pady=5)
        self.ip_var = tk.StringVar(value=DEFAULT_IP)
        self.ip_entry = ttk.Entry(conn, textvariable=self.ip_var, width=20)
        self.ip_entry.grid(row=0, column=1, sticky="ew", padx=(0, pad), pady=5)

        ttk.Label(conn, text="Port").grid(row=0, column=2, sticky="e", padx=(pad, 5), pady=5)
        self.port_var = tk.StringVar(value=str(DEFAULT_PORT))
        self.port_entry = ttk.Entry(conn, textvariable=self.port_var, width=8)
        self.port_entry.grid(row=0, column=3, sticky="ew", padx=(0, pad), pady=5)

        ttk.Label(conn, text="Message").grid(row=1, column=0, sticky="e", padx=(pad, 5), pady=(0,5))
        self.msg_var = tk.StringVar(value=DEFAULT_MESSAGE)
        self.msg_entry = ttk.Entry(conn, textvariable=self.msg_var)
        self.msg_entry.grid(row=1, column=1, columnspan=3, sticky="ew", padx=(0, pad), pady=(0,5))

        # ==== Toolbar ====
        toolbar = ttk.Frame(self)
        toolbar.grid(row=1, column=0, sticky="ew", padx=pad, pady=5)

        self.send_btn = ttk.Button(toolbar, text="Send", command=self.on_send)
        self.send_btn.pack(side="left", padx=(0,5))
        self.export_btn = ttk.Button(toolbar, text="Export to TXT", command=self.export_to_txt)
        self.export_btn.pack(side="left", padx=5)
        self.clear_btn = ttk.Button(toolbar, text="Clear", command=self.clear_all)
        self.clear_btn.pack(side="left", padx=5)

        self.progress = ttk.Progressbar(toolbar, mode="indeterminate", length=120)
        self.progress.pack(side="right", padx=(5,10))
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(toolbar, textvariable=self.status_var, style="Status.TLabel").pack(side="right")

        # ==== Response Frame ====
        resp = ttk.LabelFrame(self, text="Response", style="Header.TLabelframe")
        resp.grid(row=2, column=0, sticky="nsew", padx=pad, pady=(0, pad))
        resp.grid_rowconfigure(0, weight=1)
        resp.grid_columnconfigure(0, weight=1)

        self.text = tk.Text(resp, wrap="word", height=12, font=("Consolas", 10))
        self.text.grid(row=0, column=0, sticky="nsew")
        self.text.tag_configure("time", foreground="#2a7ae2")
        self.text.tag_configure("error", foreground="#b00020")
        self.text.tag_configure("rx", foreground="#000000")

        yscroll = ttk.Scrollbar(resp, orient="vertical", command=self.text.yview)
        yscroll.grid(row=0, column=1, sticky="ns")
        self.text.configure(yscrollcommand=yscroll.set)

        # Queue for thread-safe UI updates
        self.msg_queue = queue.Queue()
        self.after(100, self._drain_queue)

        # Keyboard shortcuts
        self.bind("<Control-Return>", lambda e: self.on_send())
        self.bind("<Control-s>", lambda e: self.export_to_txt())
        self.bind("<Control-l>", lambda e: self.clear_all())

    # === UI actions ===
    def on_send(self):
        ip = self.ip_var.get().strip()
        port_s = self.port_var.get().strip()
        msg = self.msg_var.get().strip()

        if not ip or not msg:
            messagebox.showerror("Missing Info", "Please enter IP and Message.")
            return
        try:
            port = int(port_s)
            if not (0 < port < 65536):
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid Port", "Port must be between 1 and 65535.")
            return

        self._set_busy(True, f"Connecting to {ip}:{port} ...")
        threading.Thread(target=self._send_recv_worker, args=(ip, port, msg), daemon=True).start()

    def export_to_txt(self):
        content = self.text.get("1.0", "end").strip()
        if not content:
            messagebox.showwarning("No Data", "There is no response to save.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text files", "*.txt")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            messagebox.showinfo("Success", f"Response saved to {path}")
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save file:\n{e}")

    def clear_all(self):
        self.text.delete("1.0", "end")
        self.status_var.set("Ready")

    # === Worker Thread ===
    def _send_recv_worker(self, ip, port, message):
        try:
            to_send = STX + message.encode("utf-8") + ETX
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(DEFAULT_TIMEOUT)
                s.connect((ip, port))
                s.sendall(to_send)

                buf = bytearray()
                while True:
                    chunk = s.recv(BUFFER_SIZE)
                    if not chunk:
                        break
                    buf.extend(chunk)
                    if ETX in chunk:
                        break

            try:
                end = buf.index(ETX) + 1
                frame = bytes(buf[:end])
            except ValueError:
                frame = bytes(buf)

            # Decode as UTF-8 (safe fallback)
            decoded = frame.decode("utf-8", errors="replace")
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.msg_queue.put(("ok", ts, decoded))

        except Exception as e:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.msg_queue.put(("err", ts, str(e)))
        finally:
            self.msg_queue.put(("done", None, None))

    # === Message Queue Processing ===
    def _drain_queue(self):
        try:
            while True:
                kind, ts, msg = self.msg_queue.get_nowait()
                if kind == "ok":
                    self._append_timestamp(ts)
                    self._append_colored_message(msg)
                    self.status_var.set("Received data.")
                elif kind == "err":
                    self._append_log(f"[{ts}] Error: {msg}\n\n", "error")
                    self.status_var.set("Error.")
                elif kind == "done":
                    self._set_busy(False, "Ready")
        except queue.Empty:
            pass
        self.after(100, self._drain_queue)

    # === Colored Output ===
    def _append_timestamp(self, ts):
        self.text.insert("end", f"[{ts}] Received:\n", "time")

    def _append_colored_message(self, msg):
        # Define color tags
        self.text.tag_configure("stx", foreground="#007fff", font=("Consolas", 10, "bold"))  # blue
        self.text.tag_configure("etx", foreground="#ff4d4d", font=("Consolas", 10, "bold"))  # red
        self.text.tag_configure("cmd", foreground="#e6c200", font=("Consolas", 10, "bold"))  # yellow
        self.text.tag_configure("data", foreground="#00a651")  # green

        # Parse content by tokens
        tokens = msg.replace("\r", "").split()
        for token in tokens:
            # Look for STX/ETX or command keywords
            if "\x02" in token or token.startswith("<STX>"):
                self.text.insert("end", "<STX> ", "stx")
            elif "\x03" in token or token.startswith("<ETX>"):
                self.text.insert("end", "<ETX>\n\n", "etx")
            elif token.startswith("sRN"):
                self.text.insert("end", token + " ", "cmd")
            elif token.startswith("LMD"):
                self.text.insert("end", token + " ", "data")
            else:
                self.text.insert("end", token + " ", "rx")
        self.text.insert("end", "\n")
        self.text.see("end")

    def _append_log(self, text, tag=None):
        self.text.insert("end", text, tag)
        self.text.see("end")

    def _set_busy(self, busy, status):
        self.status_var.set(status)
        if busy:
            self.send_btn.state(["disabled"])
            self.export_btn.state(["disabled"])
            self.clear_btn.state(["disabled"])
            self.progress.start(10)
        else:
            self.send_btn.state(["!disabled"])
            self.export_btn.state(["!disabled"])
            self.clear_btn.state(["!disabled"])
            self.progress.stop()


if __name__ == "__main__":
    app = TCPClientApp()
    app.mainloop()
