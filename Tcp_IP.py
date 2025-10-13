import socket
import tkinter as tk
from tkinter import messagebox, scrolledtext, filedialog
from datetime import datetime  # <--- Added for timestamping

# Constants
STX = b'\x02'
ETX = b'\x03'
BUFFER_SIZE = 4096

DEFAULT_IP = "192.168.0.1"
DEFAULT_PORT = 2111
DEFAULT_MESSAGE = "sRN LMDscandata"

def send_and_receive():
    ip = ip_entry.get().strip()
    port = port_entry.get().strip()
    message = message_entry.get().strip()

    try:
        port = int(port)
    except ValueError:
        messagebox.showerror("Invalid Port", "Port must be an integer.")
        return

    if not ip or not message:
        messagebox.showerror("Missing Info", "Please enter IP, port, and message.")
        return

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5)
            s.connect((ip, port))

            to_send = STX + message.encode('utf-8') + ETX
            s.sendall(to_send)

            response = b""
            while True:
                chunk = s.recv(BUFFER_SIZE)
                if not chunk:
                    break
                response += chunk
                if ETX in chunk:
                    break

            # Get timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            decoded = response.decode('utf-8', errors='replace')

            response_text.insert(tk.END, f"\n[{timestamp}] Received:\n{decoded}\n")
            response_text.see(tk.END)

    except Exception as e:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        response_text.insert(tk.END, f"\n[{timestamp}] Error: {e}\n")
        response_text.see(tk.END)

def export_to_txt():
    response = response_text.get("1.0", tk.END).strip()
    if not response:
        messagebox.showwarning("No Data", "There is no response to save.")
        return

    file_path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text files", "*.txt")])
    if file_path:
        try:
            with open(file_path, 'w') as file:
                file.write(response)
            messagebox.showinfo("Success", f"Response saved to {file_path}")
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save file: {e}")

def clear_fields():
    ip_entry.delete(0, tk.END)
    port_entry.delete(0, tk.END)
    message_entry.delete(0, tk.END)
    response_text.delete("1.0", tk.END)
    ip_entry.insert(0, DEFAULT_IP)
    port_entry.insert(0, str(DEFAULT_PORT))
    message_entry.insert(0, DEFAULT_MESSAGE)

# GUI Setup
root = tk.Tk()
root.title("TCP Client with STX/ETX")

root.grid_rowconfigure(4, weight=1)
root.grid_columnconfigure(1, weight=1)

tk.Label(root, text="IP Address:").grid(row=0, column=0, sticky='e')
ip_entry = tk.Entry(root)
ip_entry.insert(0, DEFAULT_IP)
ip_entry.grid(row=0, column=1, sticky="ew")

tk.Label(root, text="Port:").grid(row=1, column=0, sticky='e')
port_entry = tk.Entry(root)
port_entry.insert(0, str(DEFAULT_PORT))
port_entry.grid(row=1, column=1, sticky="ew")

tk.Label(root, text="Message:").grid(row=2, column=0, sticky='e')
message_entry = tk.Entry(root, width=40)
message_entry.insert(0, DEFAULT_MESSAGE)
message_entry.grid(row=2, column=1, sticky="ew")

# Frame for buttons
button_frame = tk.Frame(root)
button_frame.grid(row=3, column=0, columnspan=2, pady=5)

send_button = tk.Button(button_frame, text="Send", command=send_and_receive)
send_button.pack(side=tk.LEFT, padx=5)

export_button = tk.Button(button_frame, text="Export to TXT", command=export_to_txt)
export_button.pack(side=tk.LEFT, padx=5)

clear_button = tk.Button(button_frame, text="Clear", command=clear_fields)
clear_button.pack(side=tk.LEFT, padx=5)

tk.Label(root, text="Response:").grid(row=4, column=0, sticky='ne', padx=5)
response_text = scrolledtext.ScrolledText(root, width=60, height=10, wrap=tk.WORD)
response_text.grid(row=4, column=1, padx=5, pady=5, sticky='nsew')

root.mainloop()
