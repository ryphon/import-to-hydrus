import os
from datetime import datetime
import json
import hydrus_api
import hydrus_api
import hydrus_api.utils
from hydrus_api import ImportStatus
import numpy as np
from tempfile import TemporaryFile
from PIL.PngImagePlugin import PngInfo
from PIL import Image

REQUIRED_PERMISSIONS = (hydrus_api.Permission.IMPORT_FILES, hydrus_api.Permission.ADD_TAGS)
hydrus_key = os.environ.get("HYDRUS_KEY")
hydrus_url = os.environ.get("HYDRUS_URL")

# image I/O
def get_timestamp(time_format="%Y-%m-%d-%H%M%S"):
    now = datetime.now()
    try:
        timestamp = now.strftime(time_format)
    except:
        timestamp = now.strftime("%Y-%m-%d-%H%M%S")

    return(timestamp)

def get_hydrus_client():
    global hydrus_key
    global hydrus_url
    if hydrus_key is not None and hydrus_url is not None:
        return hydrus_api.Client(hydrus_key, hydrus_url)

    # Check for API key in file as a backup, not recommended
    # Example:
    # hydrus_api.txt
    #{
    #    "hydrus_key": "0150d9c4f6a6d2082534a997f4588dcf0c56dffe1d03ffbf98472236112236ae",
    #    "hydrus_url": "http://localhost:45869"
    #}
    try:
        if not hydrus_key and not hydrus_url:
            dir_path = os.path.dirname(os.path.realpath(__file__))
            with open(os.path.join(dir_path, "hydrus_api.txt"), "r") as f:
                keys = json.loads(f.read().strip())
                hydrus_key = keys['hydrus_key']
                hydrus_url = keys['hydrus_url']
            # Validate the key is not empty
            if keys.strip() == "":
                raise Exception(f"API Key is required to save the image outputs to Hydrus. \n PLease set the HYDRUS_API_KEY environment variable to your API key, \n and HYDRUS_API_URL to your API URL or place in {dir_path}/hydrus_api.txt.")

    except Exception as e:
        print(f"API Key is required to save the image outputs to Hydrus. \n PLease set the HYDRUS_API_KEY environment variable to your API key, \n and HYDRUS_API_URL to your API URL or place in hydrus_api.txt.")

    return hydrus_api.Client(hydrus_key, hydrus_url)

class Hydrus:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
                    "required": {
                        "images": ("IMAGE", ),
                    },
                    "optional": {
                        "positive": ("STRING",{ "multiline": True, "forceInput": True}, ),
                        "negative": ("STRING",{"multiline": True, "forceInput": True}, ),
                        "modelname": ("STRING",{"default": '', "multiline": False, "forceInput": True},),
                        "loras": ("STRING",{"default": "", "forceInput": False},),
                        "info": ("INFO",),
                        "tags": ("STRING",{"default": "ai, comfyui, hyshare: ai", "forceInput": True},),
                    },
                    "hidden": {
                        "prompt": "PROMPT",
                        "extra_pnginfo": "EXTRA_PNGINFO"
                    },
                }

    RETURN_TYPES = []
    FUNCTION = "wtf"

    OUTPUT_NODE = True

    CATEGORY = "Hydrus"

    def wtf(self, images, positive="", negative="", modelname="", loras="", info={}, tags="", prompt=None, extra_pnginfo=None):
        client = get_hydrus_client()
        imagelist = []
        split = tags.split(',')
        meta = []
        if positive != "":
            meta.append('positive: {}'.format(positive))
        if negative != "":
            meta.append('negative: {}'.format(negative))
        if modelname != "":
            meta.append('modelname: {}'.format(modelname))
        if loras != []:
            for lora in loras:
                meta.append('lora: {}'.format(lora))
        if info != {}:
            meta.append('seed: {}'.format(info['Seed: ']))
            meta.append('steps: {}'.format(info['Steps: ']))
            meta.append('cfg: {}'.format(info['CFG scale: ']))
            meta.append('sampler: {}'.format(info['Sampler: ']))
            meta.append('scheduler: {}'.format(info['Scheduler: ']))
        metatags = meta + split
        
        for image in images:
            comment = ""
            i = 255. * image.cpu().numpy()
            img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))
            # Setting up PNG metadata
            metadata = PngInfo()
            
            if prompt is not None:
                metadata.add_text("prompt", json.dumps(prompt))
            if extra_pnginfo is not None:
                for x in extra_pnginfo:
                    metadata.add_text(x, json.dumps(extra_pnginfo[x]))
            metadata.add_text("parameters", comment)
            metadata.add_text("comment", comment)
            #self.import_image(img, metadata)
            imagefile = TemporaryFile()
            img.save(imagefile, "PNG", comment=comment, pnginfo=metadata, optimize=True)
            imagefile.seek(0)
            self.import_image(imagefile, client, metatags)
            imagefile.seek(0)
            imagelist.append(imagefile)
        return imagelist

    def get_hydrus_service_key(self, client):
        local_tags = client.get_services().get('local_tags')
        service_key = ""
        for i in local_tags:
            if i['name'] == 'my tags':
                service_key = i['service_key']
                break
        return service_key

    def add_and_tag(self, client, image, tags, tag_service_key):
        hash = ""
        result = client.add_file(image)
        if result["status"] != ImportStatus.FAILED:
            hash = result["hash"]
        client.add_tags(hashes=[hash], service_keys_to_tags={tag_service_key: tags})
        return result

    def import_image(self, image, client, tags=None):
        if not hydrus_api.utils.verify_permissions(client, REQUIRED_PERMISSIONS):
            print("The API key does not grant all required permissions:", REQUIRED_PERMISSIONS)
            return 404
        tag_service_key = self.get_hydrus_service_key(client)
        result = self.add_and_tag(client, image, tags, tag_service_key)
        return result

NODE_CLASS_MAPPINGS = {
    #IO
    "Hydrus Image Importer": Hydrus,
}
