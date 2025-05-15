import os
import sys
import hashlib
import json
import time
from prettytable import PrettyTable

VCS_DIR = ".myvcs"

def init():
    # Ask for user input if no name is provided
    name = input("Enter the repository name: ")
    
    # Create necessary directories
    os.makedirs(os.path.join(VCS_DIR, "objects"), exist_ok=True)
    os.makedirs(os.path.join(VCS_DIR, "commits"), exist_ok=True)
    open(os.path.join(VCS_DIR, "index"), "w").close()
    
    # Store repository name and creation time in config
    config = {
        "name": name,
        "created": time.ctime()
    }
    
    with open(os.path.join(VCS_DIR, "config"), "w") as f:
        json.dump(config, f, indent=2)
    
    print(f"Initialized repository: {name}")

def hash_file(filepath):
    with open(filepath, "rb") as f:
        content = f.read()
    sha = hashlib.sha1(content).hexdigest()
    with open(os.path.join(VCS_DIR, "objects", sha), "wb") as f:
        f.write(content)
    return sha

def add(filename):
    index_path = os.path.join(VCS_DIR, "index")
    if not os.path.exists(filename):
        print(f"File {filename} does not exist.")
        return
    files = set()
    if os.path.exists(index_path):
        with open(index_path) as f:
            files = set(f.read().splitlines())
    files.add(filename)
    with open(index_path, "w") as f:
        for fpath in sorted(files):
            f.write(fpath + "\n")
    print(f"Added {filename} to index.")

def commit(message):
    with open(os.path.join(VCS_DIR, "index")) as f:
        files = f.read().splitlines()
    tree = {}
    for file in files:
        if os.path.exists(file):
            blob_hash = hash_file(file)
            tree[file] = blob_hash
    commit_id = hashlib.sha1((message + str(time.time())).encode()).hexdigest()
    metadata = {
        "message": message,
        "timestamp": time.ctime(),
        "tree": tree
    }
    with open(os.path.join(VCS_DIR, "commits", commit_id), "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"Committed as {commit_id[:7]}")

def log():
    commit_dir = os.path.join(VCS_DIR, "commits")
    commits = sorted(os.listdir(commit_dir), reverse=True)
    for cid in commits:
        with open(os.path.join(commit_dir, cid)) as f:
            metadata = json.load(f)
        print(f"Commit {cid[:7]} - {metadata['timestamp']}")
        print(f"  {metadata['message']}\n")

def checkout(commit_id_prefix):
    commit_dir = os.path.join(VCS_DIR, "commits")
    matches = [f for f in os.listdir(commit_dir) if f.startswith(commit_id_prefix)]
    if not matches:
        print(f"No commit found with ID starting with '{commit_id_prefix}'")
        return
    if len(matches) > 1:
        print(f"Multiple commits found matching '{commit_id_prefix}': {matches}")
        return
    commit_id = matches[0]

    with open(os.path.join(commit_dir, commit_id), "r") as f:
        metadata = json.load(f)

    for file, blob_hash in metadata["tree"].items():
        blob_path = os.path.join(VCS_DIR, "objects", blob_hash)
        if not os.path.exists(blob_path):
            print(f"Missing blob for {file} ({blob_hash})")
            continue
        with open(blob_path, "rb") as src, open(file, "wb") as dst:
            dst.write(src.read())
        print(f"Restored {file} from commit {commit_id[:7]}")

def status():
    index_path = os.path.join(VCS_DIR, "index")
    if not os.path.exists(index_path):
        print("Repository not initialized.")
        return
    with open(index_path) as f:
        files = f.read().splitlines()
    print("Tracked files:")
    for file in files:
        print("  " + file)

def show_config():
    config_path = os.path.join(VCS_DIR, "config")
    index_path = os.path.join(VCS_DIR, "index")
    
    if os.path.exists(config_path):
        with open(config_path) as f:
            config = json.load(f)
        
        # Display the repository name and creation date
        print(f"\nRepository Name: {config.get('name')}")
        print(f"Created on: {config.get('created')}")
        
        # Create a PrettyTable for the files
        table = PrettyTable()
        table.field_names = ["Tracked Files"]

        if os.path.exists(index_path):
            with open(index_path) as f:
                files = f.read().splitlines()
                for file in files:
                    table.add_row([file])  # Add each file as a row

            print("\nTracked Files:")
            print(table)
        else:
            print("\nNo files are currently tracked.")
    else:
        print("No config found.")

def help_menu():
    print("Usage:")
    print("  python main.py init")
    print("  python main.py add <file>")
    print("  python main.py commit -m \"message\"")
    print("  python main.py log")
    print("  python main.py checkout <commit-id-prefix>")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        help_menu()
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "init":
        init()
    elif cmd == "add" and len(sys.argv) >= 3:
        add(sys.argv[2])
    elif cmd == "commit" and len(sys.argv) >= 4 and sys.argv[2] == "-m":
        commit(sys.argv[3])
    elif cmd == "log":
        log()
    elif cmd == "checkout" and len(sys.argv) >= 3:
        checkout(sys.argv[2])
    elif cmd == "status": status()
    elif cmd == "config":
        show_config()
    
    else:
        help_menu()