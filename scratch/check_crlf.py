with open("calc_terminal/ui/app.py", "rb") as f:
    chunk = f.read(5000)
    print("Has CRLF:", b"\r\n" in chunk)

