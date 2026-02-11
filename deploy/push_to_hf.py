#!/usr/bin/env python3
"""Push hf_deploy files to Hugging Face Space"""

import os
from huggingface_hub import HfApi, login

# Login with token (set HF_TOKEN environment variable)
TOKEN = os.environ.get("HF_TOKEN", "")
if not TOKEN:
    raise ValueError("Please set the HF_TOKEN environment variable")
login(token=TOKEN)

api = HfApi()

# Get username
user = api.whoami()
username = user.get("name", user.get("fullname", "unknown"))
print(f"Logged in as: {username}")

# List spaces
spaces = api.list_spaces(author=username)
space_list = list(spaces)
print(f"\nYour Spaces:")
for i, space in enumerate(space_list):
    print(f"  {i+1}. {space.id}")

if not space_list:
    print("\nNo spaces found. Please provide your Space name manually.")
else:
    print(f"\nWill push to: {space_list[0].id}")
    
    # Upload files
    REPO_ID = space_list[0].id
    LOCAL_DIR = "hf_deploy"
    
    print(f"\nUploading files from {LOCAL_DIR}...")
    
    api.upload_folder(
        folder_path=LOCAL_DIR,
        repo_id=REPO_ID,
        repo_type="space",
        commit_message="Relaxed entry conditions + added logging"
    )
    
    print(f"\n✅ Successfully pushed to https://huggingface.co/spaces/{REPO_ID}")
