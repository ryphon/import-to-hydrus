import json
import os
import hydrus_api
import requests

with open("upscale_workflow.json", "r") as file:
    prompt = json.loads(file.read())

tag = "tobeupscaledbeta"

key = os.environ.get("HYDRUS_KEY")
url = os.environ.get("HYDRUS_URL")
client = hydrus_api.Client(key, url)

def get_files_with_tag(tag, client):
    hash_list = []
    file_ids = client.search_files([tag])['file_ids']
    files_metadata = client.get_file_metadata(file_ids=file_ids)['metadata']
    for individual_file in files_metadata:
        hash_list.append(individual_file['hash'])
    return hash_list

def queue_prompt(prompt):
    p = {"prompt": prompt}
    data = json.dumps(p).encode('utf-8')
    resp =  requests.post("http://10.0.0.4:8188/prompt", data=data)
    print(resp.text)

hash_list = get_files_with_tag(tag, client)

for i in hash_list:
    prompt['59']['inputs']['hash'] = i
    queue_prompt(prompt)

