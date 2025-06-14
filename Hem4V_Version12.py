import os
import sys
import subprocess
import shutil
import urllib.request
import tempfile
import traceback
import glob
from datetime import datetime

WORKDIR = r"C:\Hem4V"
LOGDIR = os.path.join(WORKDIR, "logs")
LOGFILE = os.path.join(LOGDIR, f"log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")

WORKFLOW_STEPS = [
    "Tworzenie folderu roboczego",
    "Sprawdzanie/zainstalowanie Gita",
    "Klonowanie repozytorium",
    "Instalacja zależności",
    "Uruchomienie projektu"
]
MAX_ATTEMPTS = 2

def write_logfile(msg):
    try:
        os.makedirs(LOGDIR, exist_ok=True)
        with open(LOGFILE, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass

def log(msg):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    logline = f"[{timestamp}] {msg}"
    print(logline)
    write_logfile(logline)

def log_error(msg):
    # ANSI escape for red
    red = "\033[91m"
    reset = "\033[0m"
    full_msg = f"{red}BŁĄD: {msg}{reset}"
    print(full_msg)
    write_logfile(f"BŁĄD: {msg}")

def check_exe(cmd):
    return shutil.which(cmd) is not None

def install_git():
    git_url = "https://github.com/git-for-windows/git/releases/latest/download/Git-64-bit.exe"
    temp_path = os.path.join(tempfile.gettempdir(), "Git-64-bit.exe")
    for attempt in range(1, MAX_ATTEMPTS+1):
        try:
            log(f"Próbuję pobrać Git (próba {attempt}/{MAX_ATTEMPTS}): {git_url}")
            urllib.request.urlretrieve(git_url, temp_path)
            log(f"Pobrano instalator do: {temp_path}")
            log("Instaluję Git (tryb cichy)...")
            proc = subprocess.run([temp_path, "/VERYSILENT", "/NORESTART"], check=False, capture_output=True, text=True)
            if proc.returncode != 0:
                error_msg = (
                    f"Błąd podczas instalacji Git! Kod wyjścia: {proc.returncode}\n"
                    f"stdout: {proc.stdout.strip()}\n"
                    f"stderr: {proc.stderr.strip()}\n"
                )
                log_error(error_msg)
                if attempt == MAX_ATTEMPTS:
                    return False
                else:
                    continue
            log("Git został zainstalowany.")
            os.remove(temp_path)
            return True
        except Exception as e:
            tb = traceback.format_exc()
            error_msg = (
                f"Błąd podczas pobierania/instalacji Git: {e}\n"
                f"Szczegóły błędu:\n{tb}"
            )
            log_error(error_msg)
            if attempt == MAX_ATTEMPTS:
                return False
    return False

def ensure_git():
    if check_exe("git"):
        log("Git jest zainstalowany.")
        return True
    else:
        return install_git()

def ensure_python():
    if check_exe("python"):
        log("Python jest zainstalowany.")
        return True
    else:
        msg = "Python nie jest zainstalowany! Przerwij i doinstaluj Pythona."
        log_error(msg)
        return False

def ensure_npm():
    if check_exe("npm"):
        log("Node.js (npm) jest zainstalowany.")
        return True
    else:
        msg = "Node.js / npm nie jest zainstalowany! Przerwij i doinstaluj Node.js."
        log_error(msg)
        return False

def run_cmd(cmd, cwd=None, shell=False):
    log(f"Uruchamiam: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    for attempt in range(1, MAX_ATTEMPTS+1):
        try:
            proc = subprocess.Popen(cmd, cwd=cwd, shell=shell, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in proc.stdout:
                log(line.rstrip())
            proc.wait()
            if proc.returncode != 0:
                error_msg = f"Błąd! Kod wyjścia: {proc.returncode}"
                log_error(error_msg)
                if attempt == MAX_ATTEMPTS:
                    return proc.returncode
                else:
                    log(f"Ponawiam próbę ({attempt+1}/{MAX_ATTEMPTS}) ...")
                    continue
            return 0
        except Exception as e:
            tb = traceback.format_exc()
            error_msg = f"Błąd podczas uruchamiania polecenia: {e}\nSzczegóły błędu:\n{tb}"
            log_error(error_msg)
            if attempt == MAX_ATTEMPTS:
                return -1
    return -1

def parse_repo_name(repo_url):
    name = repo_url.rstrip('/').split('/')[-1]
    if name.endswith('.git'):
        name = name[:-4]
    return name

def find_python_entrypoint(target_dir):
    candidates = ["main.py", "app.py", "index.py"]
    for fname in candidates:
        path = os.path.join(target_dir, fname)
        if os.path.isfile(path):
            return fname
    pyfiles = [os.path.basename(f) for f in glob.glob(os.path.join(target_dir, "*.py"))]
    if len(pyfiles) == 1:
        return pyfiles[0]
    elif len(pyfiles) > 1:
        print("Nie znaleziono jednoznacznego pliku startowego. Możliwe pliki:")
        for idx, f in enumerate(pyfiles):
            print(f"{idx+1}. {f}")
        while True:
            try:
                choice = int(input("Podaj numer pliku do uruchomienia: "))
                if 1 <= choice <= len(pyfiles):
                    return pyfiles[choice-1]
            except Exception:
                pass
            print("Nieprawidłowy wybór.")
    else:
        return None

def do_workflow(repo_url):
    step_idx = 0

    def progress():
        percent = int((step_idx / len(WORKFLOW_STEPS)) * 100)
        print(f"Postęp: {percent}% — Krok {step_idx}/{len(WORKFLOW_STEPS)}: {WORKFLOW_STEPS[step_idx-1] if step_idx>0 else ''}")

    try:
        # 1. Tworzenie folderu roboczego
        progress()
        log(f"Tworzę folder roboczy: {WORKDIR}")
        os.makedirs(WORKDIR, exist_ok=True)
        step_idx += 1
        progress()

        # 2. Git
        log("Sprawdzam/zainstaluję Git...")
        if not ensure_git():
            log_error("Nie udało się zainstalować Git! Przerwij i popraw środowisko.")
            return
        step_idx += 1
        progress()

        # 3. Klonowanie repozytorium
        repo_name = parse_repo_name(repo_url)
        target_dir = os.path.join(WORKDIR, repo_name)
        if os.path.exists(target_dir):
            log(f"Usuwam istniejący folder {target_dir} ...")
            try:
                shutil.rmtree(target_dir)
            except Exception as e:
                error_msg = f"Nie mogę usunąć folderu: {e}"
                log_error(error_msg)
                return
        log(f"Klonuję repozytorium...")
        exit_code = run_cmd(["git", "clone", repo_url], cwd=WORKDIR)
        if exit_code != 0:
            log_error("Błąd podczas klonowania repozytorium!")
            return
        log(f"Sklonowano do {target_dir}")
        step_idx += 1
        progress()

        # 4. Instalacja zależności
        req_path = os.path.join(target_dir, "requirements.txt")
        pkg_path = os.path.join(target_dir, "package.json")
        if os.path.isfile(req_path):
            log("Wykryto projekt Python (requirements.txt).")
            if not ensure_python():
                return
            log("Instaluję zależności: pip install -r requirements.txt")
            exit_code = run_cmd([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], cwd=target_dir)
            if exit_code != 0:
                log_error("Błąd podczas instalowania zależności pip!")
                return
        elif os.path.isfile(pkg_path):
            log("Wykryto projekt Node.js (package.json).")
            if not ensure_npm():
                return
            log("Instaluję zależności npm ...")
            exit_code = run_cmd(["npm", "install"], cwd=target_dir)
            if exit_code != 0:
                log_error("Błąd podczas npm install!")
                return
        else:
            msg = "Nie wykryto obsługiwanej technologii (brak requirements.txt / package.json)!"
            log_error(msg)
            return
        step_idx += 1
        progress()

        # 5. Uruchomienie projektu
        if os.path.isfile(req_path):
            entry_py = find_python_entrypoint(target_dir)
            if entry_py:
                log(f"Uruchamiam {entry_py} ...")
                run_cmd([sys.executable, entry_py], cwd=target_dir)
            else:
                msg = "Nie znaleziono pliku startowego Python – projekt nie został uruchomiony."
                log_error(msg)
        elif os.path.isfile(pkg_path):
            log("Uruchamiam npm start ...")
            run_cmd(["npm", "start"], cwd=target_dir, shell=True)
        step_idx += 1
        progress()
        log("Gotowe!")

    except Exception as e:
        tb = traceback.format_exc()
        log_error(f"Wyjątek krytyczny: {e}\n{tb}")

def main():
    print("HEM4V – Rozrusznik projektów (wersja terminalowa)")
    if len(sys.argv) > 1:
        repo_url = sys.argv[1].strip()
    else:
        repo_url = input("Podaj link do repozytorium GitHub: ").strip()
    if not repo_url or not repo_url.startswith("http"):
        log_error("Podaj poprawny link do repozytorium GitHub (https://...)")
        return
    do_workflow(repo_url)

if __name__ == "__main__":
    main()