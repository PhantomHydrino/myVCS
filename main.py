import os
import sys
import hashlib
import json
import time
from prettytable import PrettyTable
from rich.console import Console
from rich.tree import Tree
from rich.syntax import Syntax
import difflib

console = Console()

VCS_DIR = ".myvcs"

def init():
    # Ask for user input if no name is provided
    name = input("Enter the repository name: ")
    
    # Create necessary directories
    os.makedirs(os.path.join(VCS_DIR, "objects"), exist_ok=True)
    os.makedirs(os.path.join(VCS_DIR, "commits"), exist_ok=True)
    open(os.path.join(VCS_DIR, "index"), "w").close()

    # Set HEAD to point to the default branch (main)
    default_branch = "main"
    with open(os.path.join(VCS_DIR, "HEAD"), "w") as f:
        f.write(default_branch)

    
    os.makedirs(os.path.join(VCS_DIR, "branches"), exist_ok=True)

    # Create an empty branch pointer for 'main'
    with open(os.path.join(VCS_DIR, "branches", default_branch), "w") as f:
        f.write("")  # No commit yet
    
    # Store repository name and creation time in config
    config = {
        "name": name,
        "created": time.ctime()
    }
    
    with open(os.path.join(VCS_DIR, "config"), "w") as f:
        json.dump(config, f, indent=2)
    
    print(f"Initialized repository: {name} on branch '{default_branch}'")

def hash_file(filepath):
    with open(filepath, "rb") as f:
        content = f.read()
    sha = hashlib.sha1(content).hexdigest()
    with open(os.path.join(VCS_DIR, "objects", sha), "wb") as f:
        f.write(content)
    return sha

def is_repo_initialized():
    print("Checking repo initialization...")

    # 1. Search upward from current dir to find .myvcs/config
    current_dir = os.getcwd()
    vcs_dir = None
    config_path = None

    while True:
        potential_vcs_dir = os.path.join(current_dir, ".myvcs")
        potential_config = os.path.join(potential_vcs_dir, "config")
        if os.path.isfile(potential_config):
            vcs_dir = potential_vcs_dir
            config_path = potential_config
            break
        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:  # reached root without finding config
            print("No .myvcs/config found in any parent directory.")
            return False
        current_dir = parent_dir

    # 2. Read the repo name from config
    import json
    with open(config_path, "r") as f:
        try:
            config = json.load(f)
        except json.JSONDecodeError:
            print(f"Failed to parse config file at {config_path}")
            return False

    repo_name = config.get("name")
    if not repo_name:
        print(f"Config file at {config_path} does not contain a 'name' key.")
        return False

    # 3. Now vcs_dir is the path to .myvcs, use that to check required files/dirs
    required_files = ["HEAD", "index", "config", "branches", "commits", "objects"]
    for item in required_files:
        path = os.path.join(vcs_dir, item)
        if item in ["branches", "commits", "objects"]:
            if not os.path.isdir(path):
                print(f"Directory {path} missing!")
                return False
        else:
            if not os.path.isfile(path):
                print(f"File {path} missing!")
                return False

    print(f"Repo '{repo_name}' is initialized.")
    return True

def add(filename):
    
    if not is_repo_initialized():
        print("Error: No repository initialized. Run 'init' first.")
        return

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

    # Update current branch pointer safely
    with open(os.path.join(VCS_DIR, "HEAD")) as f:
        current_branch = f.read().strip()
    branch_path = os.path.join(VCS_DIR, "branches", current_branch)

    if os.path.exists(branch_path):
        try:
            with open(branch_path, "r") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            # In case it's just a plain commit id in the branch file
            with open(branch_path, "r") as f:
                data = {"commit": f.read().strip(), "parent": None}

        data["commit"] = commit_id

        with open(branch_path, "w") as f:
            json.dump(data, f, indent=2)
    else:
        # If branch pointer file does not exist, create it
        with open(branch_path, "w") as f:
            f.write(commit_id)

    print(f"Committed as {commit_id[:7]} on branch {current_branch}")


def log():
    commit_dir = os.path.join(VCS_DIR, "commits")
    commits = sorted(os.listdir(commit_dir), reverse=True)
    head_path = os.path.join(VCS_DIR, "HEAD")
    tree = Tree(":evergreen_tree: [bold green]Commit History (Rich View)[/]")

    if os.path.exists(head_path):
        with open(head_path) as f:
            current_branch = f.read().strip()
        tree.label = f":evergreen_tree: [bold green]Commit History on '{current_branch}'[/bold green]"

    if not commits:
        console.print("[bold red]No commits found.[/bold red]")
        return

    def load_commit(cid):
        with open(os.path.join(commit_dir, cid)) as f:
            return json.load(f)

    def get_file_content(blob_hash):
        blob_path = os.path.join(VCS_DIR, "objects", blob_hash)
        if os.path.exists(blob_path):
            with open(blob_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.readlines()
        return []

    prev_tree = {}

    for cid in commits:
        metadata = load_commit(cid)
        current_tree = metadata.get("tree", {})
        commit_node = tree.add(f"[yellow]Commit {cid[:7]}[/yellow] - {metadata['timestamp']}")

        # Detect and label merge commits
        parents = metadata.get("parents", [])
        if len(parents) == 2:
            commit_node.add(f"[red]Merge:[/] {parents[0][:7]} {parents[1][:7]}")
        if metadata['message'].startswith("Merge branch"):
            commit_node.add(f"[blue]Merge Info:[/] {metadata['message']}")

        commit_node.add(f"[bold]Message:[/] {metadata['message']}")

        if not current_tree:
            commit_node.add("[italic](No files committed)[/italic]")
        else:
            files_node = commit_node.add("[bold]Files committed:[/bold]")
            for filename in current_tree:
                files_node.add(filename)

            changes_node = commit_node.add("[bold]Changes:[/bold]")

            all_files = set(current_tree.keys()).union(prev_tree.keys())

            for filename in all_files:
                old_blob = prev_tree.get(filename)
                new_blob = current_tree.get(filename)

                old_lines = get_file_content(old_blob) if old_blob else []
                new_lines = get_file_content(new_blob) if new_blob else []

                if old_lines == new_lines:
                    continue

                diff = list(difflib.unified_diff(
                    old_lines, new_lines,
                    fromfile=f"prev/{filename}" if old_blob else "/dev/null",
                    tofile=f"curr/{filename}" if new_blob else "/dev/null",
                    lineterm=""
                ))

                if diff:
                    diff_text = "".join(diff)
                    syntax = Syntax(diff_text, "diff", theme="monokai", line_numbers=False)
                    changes_node.add(f"Changes in {filename}:").add(syntax)

        prev_tree = current_tree

    console.print(tree)

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


def merge(source_branch):
    # Load HEAD current branch
    with open(os.path.join(VCS_DIR, "HEAD")) as f:
        target_branch = f.read().strip()

    if source_branch == target_branch:
        print("Cannot merge a branch into itself.")
        return

    # Load commit ids for both branches
    def load_branch_commit(branch):
        branch_path = os.path.join(VCS_DIR, "branches", branch)
        if not os.path.exists(branch_path):
            return None
        with open(branch_path) as f:
            try:
                data = json.load(f)
                return data.get("commit")
            except:
                return f.read().strip()

    target_commit_id = load_branch_commit(target_branch)
    source_commit_id = load_branch_commit(source_branch)

    if source_commit_id is None:
        print(f"Source branch '{source_branch}' does not exist or has no commits.")
        return
    if target_commit_id is None:
        print(f"Target branch '{target_branch}' has no commits, fast-forwarding...")
        # Just move the target branch pointer to source commit
        update_branch_commit(target_branch, source_commit_id)
        checkout_branch(target_branch)
        print(f"Branch '{target_branch}' fast-forwarded to '{source_commit_id[:7]}'.")
        return

    if target_commit_id == source_commit_id:
        print("Branches are already up-to-date.")
        return

    # Load trees from both commits
    def load_commit_tree(commit_id):
        commit_path = os.path.join(VCS_DIR, "commits", commit_id)
        if not os.path.exists(commit_path):
            return {}
        with open(commit_path) as f:
            data = json.load(f)
        return data.get("tree", {})

    target_tree = load_commit_tree(target_commit_id)
    source_tree = load_commit_tree(source_commit_id)

    common_ancestor = find_common_ancestor(target_commit_id, source_commit_id)
    base_tree = load_commit_tree(common_ancestor) if common_ancestor else {}

    conflicts = detect_conflicts(base_tree, source_tree, target_tree, get_file_lines)

    if conflicts:
        print("Merge conflicts detected!")
        for file, content in conflicts.items():
            print(f"\n--- Conflict in {file} ---")
            print(content)
            # Optional: Write it to file for real in-working-dir merge
            with open(file, "w") as f:
                f.write(content)
        print("\nPlease resolve conflicts manually and commit the result.")
        return

    # Naive merge: union files, source overwrites target on conflicts
    merged_tree = target_tree.copy()
    merged_tree.update(source_tree)

    # Write blobs for merged files (already saved from commits)

    # Create merge commit metadata
    message = f"Merge branch '{source_branch}' into '{target_branch}'"
    commit_id = hashlib.sha1((message + str(time.time())).encode()).hexdigest()
    metadata = {
        "message": message,
        "timestamp": time.ctime(),
        "tree": merged_tree,
        "parents": [target_commit_id, source_commit_id]
    }

    with open(os.path.join(VCS_DIR, "commits", commit_id), "w") as f:
        json.dump(metadata, f, indent=2)

    # Update target branch pointer to new merge commit
    update_branch_commit(target_branch, commit_id)

    # Checkout merged state to working directory
    checkout(commit_id)

    print(f"Merged branch '{source_branch}' into '{target_branch}' as commit {commit_id[:7]}.")

def update_branch_commit(branch, commit_id):
    branch_path = os.path.join(VCS_DIR, "branches", branch)
    if os.path.exists(branch_path):
        try:
            with open(branch_path, "r") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            with open(branch_path, "r") as f:
                data = {"commit": f.read().strip(), "parent": None}
        data["commit"] = commit_id
        with open(branch_path, "w") as f:
            json.dump(data, f, indent=2)
    else:
        with open(branch_path, "w") as f:
            f.write(commit_id)


def checkout_branch(branch_name):
    branch_path = os.path.join(VCS_DIR, "branches", branch_name)
    if not os.path.exists(branch_path):
        print(f"Branch '{branch_name}' does not exist.")
        return

    # Read commit + parent info
    with open(branch_path, "r") as f:
        try:
            data = json.load(f)
            commit_id = data.get("commit")
            parent = data.get("parent", "unknown")
        except json.JSONDecodeError:
            commit_id = f.read().strip()
            parent = "unknown"

    config_path = os.path.join(VCS_DIR, "config")
    if os.path.exists(config_path):
        with open(config_path) as f:
            config = json.load(f)
        repo_name = config.get("name", "unknown")
    else:
        repo_name = "unknown"

    # Update HEAD
    with open(os.path.join(VCS_DIR, "HEAD"), "w") as f:
        f.write(branch_name)

    # Checkout commit files (if any)
    if commit_id:
        checkout(commit_id)

    if branch_name == "main":
        print(f"Switched to branch '{branch_name}'. This branch is God — it has no parent.")
    else:
        if parent in [None, "", "unknown"]:
            origin = "unknown"
        else:
            origin = parent
            print(f"Switched to branch '{branch_name}' (derived from '{origin}') in repository '{repo_name}'")

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

def create_branch(branch_name):
    head_path = os.path.join(VCS_DIR, "HEAD")
    branches_dir = os.path.join(VCS_DIR, "branches")
    os.makedirs(branches_dir, exist_ok=True)

    if not os.path.exists(head_path):
        print("Repository not initialized or HEAD is missing.")
        return

    with open(head_path, "r") as f:
        current_branch = f.read().strip()

    current_commit = get_current_commit()
    if not current_commit:
        print("No commits yet. Commit before creating a branch.")
        return

    branch_path = os.path.join(branches_dir, branch_name)
    if os.path.exists(branch_path):
        print(f"Branch '{branch_name}' already exists.")
        return

    # Save both the commit and the parent branch name
    metadata = {
        "commit": current_commit,
        "parent": current_branch
    }

    with open(branch_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"Branch '{branch_name}' created from '{current_branch}' at commit {current_commit[:7]}")

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

def get_current_commit():
    head_path = os.path.join(VCS_DIR, "HEAD")
    if not os.path.exists(head_path):
        return None
    with open(head_path) as f:
        branch = f.read().strip()
    branch_path = os.path.join(VCS_DIR, "branches", branch)
    if os.path.exists(branch_path):
        with open(branch_path) as f:
            content = f.read()
            try:
                data = json.loads(content)
                return data.get("commit")
            except json.JSONDecodeError:
                return content.strip()
    return None

def branch_log():

    tree = Tree(":deciduous_tree: [bold green]Branch Tree[/bold green]")

    branches_dir = os.path.join(VCS_DIR, "branches")
    if not os.path.exists(branches_dir):
        print("No branches found.")
        return

    # Load all branch metadata
    branch_meta = {}
    for branch_file in os.listdir(branches_dir):
        path = os.path.join(branches_dir, branch_file)
        try:
            with open(path) as f:
                data = json.load(f)
                branch_meta[branch_file] = data
        except Exception:
            # fallback in case it's just a commit hash
            with open(path) as f:
                branch_meta[branch_file] = {"commit": f.read().strip(), "parent": None}

    # Reverse-map parent -> children
    tree_map = {}
    for branch, meta in branch_meta.items():
        parent = meta.get("parent")
        tree_map.setdefault(parent, []).append(branch)

    def build_tree(node, parent=None):
        children = tree_map.get(parent, [])
        for child in sorted(children):
            child_node = node.add(f"[cyan]{child}[/cyan]")
            build_tree(child_node, parent=child)

    build_tree(tree)

    console.print(tree)


def detect_conflicts(base_tree, source_tree, target_tree, get_file_lines):
    conflicts = {}

    all_files = set(base_tree.keys()) | set(source_tree.keys()) | set(target_tree.keys())

    for filename in all_files:
        base_hash = base_tree.get(filename)
        source_hash = source_tree.get(filename)
        target_hash = target_tree.get(filename)

        base_lines = get_file_lines(base_hash)
        source_lines = get_file_lines(source_hash)
        target_lines = get_file_lines(target_hash)

        if source_lines != base_lines and target_lines != base_lines and source_lines != target_lines:
            conflict_block = (
                "<<<<<<< HEAD\n"
                + "".join(target_lines) +
                "=======\n"
                + "".join(source_lines) +
                ">>>>>>> incoming branch\n"
            )
            conflicts[filename] = conflict_block

    return conflicts

def get_file_lines(blob_hash):
    if blob_hash is None:
        return []
    path = os.path.join(".myvcs", "objects", blob_hash)
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.readlines()

def find_common_ancestor(commit1, commit2):
    def get_parents(cid):
        commit_path = os.path.join(VCS_DIR, "commits", cid)
        if not os.path.exists(commit_path):
            return []
        with open(commit_path) as f:
            data = json.load(f)
        return data.get("parents", [])

    def walk_ancestry(start_commit):
        visited = set()
        stack = [start_commit]
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            stack.extend(get_parents(current))
        return visited

    ancestors1 = walk_ancestry(commit1)
    ancestors2 = walk_ancestry(commit2)

    # Intersection of both sets gives common ancestors
    common = ancestors1 & ancestors2
    if not common:
        return None  # No common ancestor found

    # Just return the first one for now (could add generation depth later)
    for cid in ancestors1:
        if cid in common:
            return cid
    return None


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
        if "--with-branches" in sys.argv:
            branch_log()
    elif cmd == "checkout" and len(sys.argv) >= 3:
        checkout(sys.argv[2])
    elif cmd == "status": status()
    elif cmd == "config":
        show_config()
    elif cmd == "branch" and len(sys.argv) >= 3:
        create_branch(sys.argv[2])
    elif cmd == "checkout-branch" and len(sys.argv) >= 3:
        checkout_branch(sys.argv[2])
    elif cmd == "merge" and len(sys.argv) >= 3:
        merge(sys.argv[2])
    else:
        help_menu()