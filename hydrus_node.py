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

# image I/O
def get_timestamp(time_format="%Y-%m-%d-%H%M%S"):
    now = datetime.now()
    try:
        timestamp = now.strftime(time_format)
    except:
        timestamp = now.strftime("%Y-%m-%d-%H%M%S")

    return(timestamp)

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
                        "hydrus_api_key": ("STRING",),
                        "hydrus_api_url": ("STRING",),
                        "positive": ("STRING",{ "multiline": True, "forceInput": True}, ),
                        "negative": ("STRING",{"multiline": True, "forceInput": True}, ),
                        "modelname": ("STRING",{"default": '', "multiline": False, "forceInput": True}),
                        "info": ("INFO",),
                        "tags": ("STRING",{"default": "ai, comfyui, hyshare: ai", "forceInput": True}),
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

    def wtf(self, images=[], hydrus_api_key="", hydrus_api_url="", positive="", negative="", modelname="", info={}, tags="", prompt=None, extra_pnginfo=None):
        client = hydrus_api.Client(hydrus_api_key, hydrus_api_url)
        imagelist = []
        split = tags.split()
        meta = []
        if positive != "":
            meta.append('positive: {}'.format(positive))
        if negative != "":
            meta.append('negative: {}'.format(negative))
        if modelname != "":
            meta.append('modelname: {}'.format(modelname))
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
