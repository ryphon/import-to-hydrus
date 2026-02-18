"""
Utility script for queuing upscaling workflows for files matching a tag.
"""

import json
import os
import requests
import hydrus_api


def get_files_with_tag(tag, client):
    """Get list of file hashes matching a tag."""
    file_ids = client.search_files([tag])['file_ids']
    files_metadata = client.get_file_metadata(file_ids=file_ids)['metadata']
    return [file_meta['hash'] for file_meta in files_metadata]


def queue_prompt(prompt, comfyui_url="http://10.0.0.4:8188"):
    """Queue a prompt for processing on ComfyUI."""
    payload = {"prompt": prompt}
    data = json.dumps(payload).encode('utf-8')
    response = requests.post(f"{comfyui_url}/prompt", data=data)
    print(f"Queue response: {response.text}")
    return response


def main():
    """Queue upscaling workflow for all files with tobeupscaledbeta tag."""
    # Load configuration
    with open("upscale_workflow.json", "r") as file:
        prompt = json.loads(file.read())

    # Initialize Hydrus client
    key = os.environ.get("HYDRUS_KEY")
    url = os.environ.get("HYDRUS_URL")
    if not key or not url:
        raise ValueError("HYDRUS_KEY and HYDRUS_URL environment variables required")
    
    client = hydrus_api.Client(key, url)

    # Get files to upscale
    tag = "tobeupscaledbeta"
    hash_list = get_files_with_tag(tag, client)
    
    print(f"Found {len(hash_list)} files to upscale")
    
    # Queue each file for upscaling
    for hash_val in hash_list:
        prompt['59']['inputs']['hash'] = hash_val
        queue_prompt(prompt)


if __name__ == "__main__":
    main()


