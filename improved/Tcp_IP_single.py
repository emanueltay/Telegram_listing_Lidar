#!/usr/bin/env python3
import argparse
import socket
from datetime import datetime

STX = b'\x02'
ETX = b'\x03'
BUFFER_SIZE = 4096

DEFAULT_IP = "192.168.0.1"
DEFAULT_PORT = 2111
DEFAULT_MESSAGE = "sRN LMDscandata"
DEFAULT_TIMEOUT = 5.0  # seconds


def fetch_once(ip: str, port: int, message: str, timeout: float) -> bytes:
    """
    Connects to (ip, port), sends STX + message + ETX, and returns the first frame received.
    Reads until ETX is seen or the socket closes.
    """
    to_send = STX + message.encode("utf-8") + ETX

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
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

    # If multiple frames or extra data, keep only up to and including the first ETX
    try:
        end = buf.index(ETX) + 1
        frame = bytes(buf[:end])
    except ValueError:
        # ETX not found; return whatever we got
        frame = bytes(buf)

    return frame


def strip_framing(data: bytes) -> bytes:
    """Remove leading STX and the first trailing ETX, if present."""
    if data.startswith(STX):
        data = data[1:]
    try:
        etx_pos = data.index(ETX)
        data = data[:etx_pos]
    except ValueError:
        pass
    return data


def main():
    ap = argparse.ArgumentParser(description="One-shot TCP client with STX/ETX framing.")
    ap.add_argument("--ip", default=DEFAULT_IP, help=f"Target IP (default: {DEFAULT_IP})")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Target port (default: {DEFAULT_PORT})")
    ap.add_argument("--msg", default=DEFAULT_MESSAGE, help=f"Message to send (default: '{DEFAULT_MESSAGE}')")
    ap.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help=f"Socket timeout in seconds (default: {DEFAULT_TIMEOUT})")
    ap.add_argument("--raw", action="store_true", help="Print raw bytes as hex instead of decoded text")
    ap.add_argument("--keep-control", action="store_true", help="Keep STX/ETX in output (default strips them)")
    args = ap.parse_args()

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        frame = fetch_once(args.ip, args.port, args.msg, args.timeout)

        # Optionally strip STX/ETX for cleaner output
        payload = frame if args.keep_control else strip_framing(frame)


        print(f"[{timestamp}] Received:")
        if args.raw:
            print(payload.hex(" "))
        else:
            # Decode safely; show replacement chars for undecodable bytes
            print(payload.decode("utf-8", errors="replace"))

    except Exception as e:
        print(f"[{timestamp}] Error: {e}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
