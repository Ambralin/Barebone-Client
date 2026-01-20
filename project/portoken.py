import os
import string

def find_lockfile():
    """Search all drives for the League lockfile and return its path, or None."""
    for drive in string.ascii_uppercase:
        path = f"{drive}:\\Riot Games\\League of Legends\\League of Legends\\lockfile"
        if os.path.exists(path):
            return path
    return None

def get_lcu_token_and_port():
    """Return (token, port) tuple from the lockfile, or (None, None) if not found."""
    lockfile_path = find_lockfile()
    if not lockfile_path:
        return None, None

    with open(lockfile_path, "r") as f:
        parts = f.read().strip().split(":")
        if len(parts) == 5:
            _, _, port, token, _ = parts
            return token, int(port)
    return None, None

def main():
    token, port = get_lcu_token_and_port()
    if token and port:
        print(f"Found LCU Token: {token}")
        print(f"LCU Port: {port}")
    else:
        print("Lockfile not found or invalid.")

if __name__ == "__main__":
    main()