# config.py

import os

# Get the directory where this config.py file is located.
# This makes our path references robust and independent of where the script is run from.
_project_root = os.path.dirname(os.path.abspath(__file__))

# --- Core Paths ---
# IMPORTANT: Replace these placeholder paths with the actual paths on your system.
# Use forward slashes '/' for paths to avoid issues, even on Windows.
PHYSICAL_DRIVE_PATHS = {
    'D': 'D:\\PoolPart.bff64b92-d745-4ff9-933b-ae092c32cfc7',
    'E': 'E:\\PoolPart.46e9a8f6-1019-4e8f-af54-ec2673cb3a28',
    'F': 'F:\\PoolPart.c3eea89e-5163-4f85-89fa-8720729cda69',
    'H': 'H:\\PoolPart.8698780e-2b8d-41bb-9da1-e00739184da7',
    'I': 'I:\\PoolPart.40c6f0c7-d2ec-467b-8cb7-a40c43b96728',
    'K': 'K:\\PoolPart.3bbf55df-af05-4d1b-8f4d-42e7257c5744',
    'Q': 'Q:\\PoolPart.360536be-a733-4484-b8c5-fdefe3d00e89',
    'U': 'U:\\PoolPart.6610f243-02f1-4552-ae81-c9fdae7722fe',
    'V': 'V:\\PoolPart.cd8bed16-b13c-4f35-967a-1abb245bc3eb',
    'Z': 'Z:\\PoolPart.352400c4-6432-4d03-8f76-aa21f2591ba3'
}

VIRTUAL_DOWNLOADS_PATH = "M:\\Downloads"
VIRTUAL_MEDIA_PATH = "M:\\Media"

# --- Database ---
DB_FILE_PATH = os.path.join(_project_root, "media_linker.sqlite")

# --- Logging ---
LOG_FILE_PATH = os.path.join(_project_root, "media_linker.log")

# --- Hashing ---
# Number of parallel processes to use for hashing files.
# A good starting point is the number of CPU cores you have. 16 is aggressive and I/O limited.
HASHING_WORKERS = 10

# --- qBittorrent ---
# IMPORTANT: Replace with your qBittorrent WebUI credentials and address.
QBITTORRENT_HOST = "192.168.0.20"
QBITTORRENT_PORT = 8777
QBITTORRENT_USERNAME = "mvl"
QBITTORRENT_PASSWORD = "@lpha0mega" # Replace with your actual password

# --- Symlinking ---
# The temporary suffix to add to files before they are replaced with a symlink.
BACKUP_SUFFIX = ".bak"