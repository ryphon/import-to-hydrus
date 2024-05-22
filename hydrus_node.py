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
                        "filename": ("STRING", {"default": f'%time_%seed', "multiline": False}),
                        "extension": (['png', 'jpeg', 'tiff', 'gif'], ),
                        "quality": ("INT", {"default": 100, "min": 1, "max": 100, "step": 1}),
                    },
                    "optional": {
                        "positive": ("STRING",{ "multiline": True, "forceInput": True}, ),
                        "negative": ("STRING",{"multiline": True, "forceInput": True}, ),
                        "seed": ("INT",{"default": 0, "min": 0, "max": 0xffffffffffffffff, "forceInput": True}),
                        "modelname": ("STRING",{"default": '', "multiline": False, "forceInput": True}),
                        "counter": ("INT",{"default": 0, "min": 0, "max": 0xffffffffffffffff }),
                        "time_format": ("STRING", {"default": "%Y-%m-%d-%H%M%S", "multiline": False}),
                        "info": ("INFO",)
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

    def wtf(self, images, filename, extension, quality, positive=None, negative=None, seed=None, modelname=None, counter=None, time_format=None, info=None, prompt=None, extra_pnginfo=None):
        print("Images: ", images)
        imagelist = []
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
            print("Image File: ", imagefile)
            imagefile.seek(0)
            self.import_image(imagefile)
            imagelist.append(imagefile)


        return imagelist

    def debug(self, images, filename, extension, quality, positive=None, negative=None, seed=None, modelname=None, counter=None, time_format=None, info=None, prompt=None, extra_pnginfo=None):
        print("Images: ", images)
        print("Filename: ", filename)
        print("Extension: ", extension)
        print("Quality: ", quality)
        print("Positive: ", positive)
        print("Negative: ", negative)
        print("Seed: ", seed)
        print("Modelname: ", modelname)
        print("Counter: ", counter)
        print("Time Format: ", time_format)
        print("Info: ", info)
        print("Prompt: ", prompt)
        print("Extra PNGInfo: ", extra_pnginfo)
        return 'yay'

    def make_tags(self, metadata=None):
        tags = ['ai', 'comfyui', 'hyshare: ai']
        return tags

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
        print(result)
        if result["status"] != ImportStatus.FAILED:
            hash = result["hash"]
        print(hash)
        client.add_tags(hashes=[hash], service_keys_to_tags={tag_service_key: tags})
        return result


    def import_image(self, image, metadata=None):
        api_url = ""
        api_key = ""
        client = hydrus_api.Client(api_key, api_url)
        if not hydrus_api.utils.verify_permissions(client, REQUIRED_PERMISSIONS):
            print("The API key does not grant all required permissions:", REQUIRED_PERMISSIONS)
            return 404

        tag_service_key = self.get_hydrus_service_key(client)
        tags = self.make_tags(metadata)
        result = self.add_and_tag(client, image, tags, tag_service_key)
    
        return result

NODE_CLASS_MAPPINGS = {
    #IO
    "Hydrus Image Importer": Hydrus,
}
