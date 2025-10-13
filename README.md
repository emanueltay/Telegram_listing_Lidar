# TCP Data Retrieval & Hex-to-Decimal Converter

This project contains **two simple GUI-based Python programs** for communicating with a TCP device (such as a SICK sensor) and converting received data from **hexadecimal to decimal format** for further analysis.

---

## 1. `retrieve_and_export.py` — TCP Client with STX/ETX

### 🔍 Purpose
This program allows you to connect to a TCP device, send a command framed with **STX (Start of Text)** and **ETX (End of Text)** control characters, and display the received response in real-time.  
It also provides options to **export the received data** into a `.txt` file for later processing.

### 🧩 Features
- Connects to a TCP server using IP and port.
- Automatically wraps messages with `STX` (`0x02`) and `ETX` (`0x03`).
- Displays the timestamped response in a scrollable text box.
- Supports exporting the response to a `.txt` file.
- Reset/clear fields easily with one button.

### ⚙️ Default Settings
| Setting        | Default Value     |
|----------------|-------------------|
| IP Address     | `192.168.0.1`     |
| Port Number    | `2111`            |
| Message        | `sRN LMDscandata` |

### 🖥️ GUI Overview
| Element | Description |
|----------|--------------|
| **IP Address / Port / Message** | Connection settings. |
| **Send** | Sends the message to the device. |
| **Export to TXT** | Saves all responses into a text file. |
| **Clear** | Resets input fields and clears the response log. |
| **Response Box** | Displays timestamped data or error messages. |

---

## 2. `txt_to_dec.py` — Hexadecimal to Decimal Converter

### 🔍 Purpose
This program reads a `.txt` file containing hexadecimal data (e.g., exported from the TCP client) and converts it into **decimal values** and **ASCII representations**.  
It also identifies specific text markers (like `"DIST1"`) for easier data interpretation.

### 🧩 Features
- Import `.txt` files containing hexadecimal strings.
- Convert each hex value into:
  - **Decimal equivalent**
  - **ASCII character** (if printable)
- Displays two synchronized panels:
  - Left: Hexadecimal values  
  - Right: Decimal equivalents
- Highlights `"DIST1"` markers for readability.
- Clear button to reset both panels.

### 🖥️ GUI Overview
| Element | Description |
|----------|--------------|
| **Import TXT and Convert** | Selects a `.txt` file and processes it. |
| **Clear** | Clears both hex and decimal displays. |
| **Hex Values Panel** | Shows the original hexadecimal strings. |
| **Decimal Values Panel** | Shows the converted decimal numbers and ASCII interpretation. |

---

## 🧰 Requirements
Both programs use **only standard Python libraries** — no external installations required.

| Library | Purpose |
|----------|----------|
| `socket` | Handles TCP connections. |
| `tkinter` | Builds the graphical user interface. |
| `datetime` | Adds timestamps to responses. |

✅ Works on **Windows 10/11**, **Python 3.8+**

---

## ▶️ How to Run
1. Ensure Python is installed (Python 3.8 or newer).
2. Open a terminal in the project folder.
3. Run the desired script:
   ```bash
   python retrieve_and_export.py
