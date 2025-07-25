import os
from datetime import datetime
import json
import time
import hashlib
import torch
import comfy
from comfy import sd
import hydrus_api
import hydrus_api.utils
from hydrus_api import ImportStatus
import folder_paths
import numpy as np
from tempfile import TemporaryFile
from PIL.PngImagePlugin import PngInfo
from PIL import Image

REQUIRED_PERMISSIONS = (hydrus_api.Permission.IMPORT_FILES, hydrus_api.Permission.ADD_TAGS)
hydrus_key = os.environ.get("HYDRUS_KEY")
hydrus_url = os.environ.get("HYDRUS_URL")
hydrus_logging_prefix = "\033[0;34m[\033[0;39mHydrus\033[0;34m]\033[0;39m"

# image I/O
def get_timestamp(time_format="%Y-%m-%d-%H%M%S"):
    now = datetime.now()
    try:
        timestamp = now.strftime(time_format)
    except:
        timestamp = now.strftime("%Y-%m-%d-%H%M%S")

    return(timestamp)

def get_hydrus_service_key(client):
    local_tags = client.get_services().get('local_tags')
    service_key = ""
    for i in local_tags:
        if i['name'] == 'my tags':
            # Currently hard coded to 'my tags' service.
            # TODO: Let the tag service be dynamically chosen based on input
            service_key = i['service_key']
            break
    return service_key

def get_hydrus_client():
    # Create a Hydrus client based on env vars or files. This is extremely unlikely to change in any meaningful time
    global hydrus_key
    global hydrus_url
    if hydrus_key is not None and hydrus_url is not None:
        return hydrus_api.Client(hydrus_key, hydrus_url)

    # Check for API key in file as a backup, not recommended
    # Example, note this isn't a real API key:
    # hydrus_api.txt
    #{
    #    "hydrus_key": "0150d9c4f6a6d2082534a997f4588dcf0c56dffe1d03ffbf98472236112236ae",
    #    "hydrus_url": "http://localhost:45869"
    #}
    try:
        if not hydrus_key and not hydrus_url:
            dir_path = os.path.dirname(os.path.realpath(__file__))
            # dir usually ends up being ComfyUI/custom_nodes/import-to-hydrus/hydrus_api.txt
            with open(os.path.join(dir_path, "hydrus_api.txt"), "r") as f:
                api_file = json.loads(f.read())
                hydrus_key = api_file['hydrus_key']
                hydrus_url = api_file['hydrus_url']
            # Validate the key is not empty
            if api_file.keys() == "":
                raise Exception(f"API Key is required to save the image outputs to Hydrus. \n PLease set the HYDRUS_API_KEY environment variable to your API key, \n and HYDRUS_API_URL to your API URL or place in {dir_path}/hydrus_api.txt.")

    except Exception as e:
        print("Exception: {}".format(e))
        print("{} API Key is required to save the image outputs to Hydrus. \n{} Please set the HYDRUS_API_KEY environment variable to your API key, \n{} and HYDRUS_API_URL to your API URL or place in hydrus_api.txt.".format(hydrus_logging_prefix, hydrus_logging_prefix, hydrus_logging_prefix))

    return hydrus_api.Client(hydrus_key, hydrus_url)

class HydrusExport:
    def __init__(self):
       self.client = get_hydrus_client()

    @classmethod
    def INPUT_TYPES(cls):
        input_dir = folder_paths.get_input_directory()
        files = [f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))]
        return {
                    "required": {
                    },
                    "optional": {
                        "images": (sorted(files), {"image_upload": False},),
                        "tag": ("STRING",{"default": '', "multiline": False, "forceInput": True},),
                        "hash": ("STRING",{"default": '', "multiline": False, "forceInput": True},),
                        "usetag": ("BOOLEAN", {"default": False},),
                        "usehash": ("BOOLEAN", {"default": False},)
                    },
                    "hidden": {
                    },
                }


    RETURN_TYPES = ["IMAGE", "MODEL", "CLIP", "VAE", "STRING",   "STRING",   "STRING",    "STRING", "STRING"]
    RETURN_NAMES = ["image", "model", "clip", "vae", "positive", "negative", "modelname", "seed",   "loras"]
    FUNCTION = "export_from_hydrus"

    OUTPUT_NODE = False

    CATEGORY = "image"
    # I had this in Hydrus originally, honestly smarter to just have it alongside the other image savers

    def get_files_with_tag(self, tag):
        hash_list = []
        file_ids = self.client.search_files([tag])['file_ids']
        files_metadata = self.client.get_file_metadata(file_ids=file_ids)['metadata']
        for individual_file in files_metadata:
            hash_list.append(individual_file['hash'])
        return hash_list

    def get_file_metadata(self, hash):
        metadata = self.client.get_file_metadata(hashes={hash})['metadata'][0]
        tag_service = get_hydrus_service_key(self.client)
        tags = metadata['tags'][tag_service]['display_tags']['0']
        outputs = {}
        outputs['loras'] = []
        for i in tags:
            if 'modelname:' in i:
                outputs['modelname'] = i.replace('modelname:','')
            if 'positive:' in i:
                outputs['positive'] = i.replace('positive:','')
            if 'negative:' in i:
                outputs['negative'] = i.replace('negative:','')
            if 'seed:' in i:
                outputs['seed'] = i.replace('seed:','')
            if 'lora:' in i:
                outputs['loras'].append(i.replace('lora:',''))
        return outputs

    def get_file(self, hash):
        file = self.client.get_file(hash)
        response = file.content
        return response

    def checkpointer(self, ckpt_name=""):
        ckpt_path = folder_paths.get_full_path('checkpoints', ckpt_name)
        out = sd.load_checkpoint_guess_config(ckpt_path, output_vae=True, output_clip=True)
        new_out = list(out)
        new_out.pop()
        out = tuple(new_out)
        return out

    def parse_name(self, ckpt_name):
        path = ckpt_name
        filename = path.split("/")[-1]
        filename = filename.split(".")[:-1]
        filename = ".".join(filename)
        return filename

    def prep_image(self, hash):
        tags = self.get_file_metadata(hash)
        model = '{}.safetensors'.format(tags['modelname'])
        # add something to search the models directory
        out = self.checkpointer(model)
        hydrus = TemporaryFile()
        hydrus_file = self.get_file(hash)
        hydrus.write(hydrus_file)
        img = Image.open(hydrus)
        image = img.convert("RGB")
        image = np.array(image).astype(np.float32) / 255.0
        image = torch.from_numpy(image)[None,]
        image_tuple = (image, )
        model_tuple = out
        tag_tuple = (tags['positive'], tags['negative'], tags['modelname'], tags['seed'], tags['loras'])
        returned = image_tuple + model_tuple + tag_tuple
        return returned

    def export_from_hydrus(self, images="", tag="", hash="", usehash=False, usetag=False):
        return_batch = []
        if usetag:
            hash_list = self.get_files_with_tag(tag)
            for hash in hash_list:
                return_batch.append(self.prep_image(hash))
        elif usehash:
            return_batch.append(self.prep_image(hash))
        else:
            image_path = folder_paths.get_annotated_filepath(images, './')
            # The SDBatch Loader I'm using is weird, defaulting this to './' allowed to be pulled from input/ToBeUpscaled
            print("{} Image: {}".format(hydrus_logging_prefix, images))
            with open(image_path,'rb') as file:
                hash = hashlib.sha256(file.read()).hexdigest()
                return_batch.append(self.prep_image(hash))
        return return_batch[0]

class HydrusDuplicates:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
                    "required": {
                        "original_hash": ("STRING",{ "multiline": True, "forceInput": True}, ),
                        "upscaled_hash": ("STRING",{ "multiline": True, "forceInput": True}, ),
                    },
                    "optional": {
                    },
                    "hidden": {
                    },
                }

    RETURN_TYPES = []
    FUNCTION = "dedupe"

    OUTPUT_NODE = True

    CATEGORY = "image"

#{
#  "relationships" : [
#    {
#      "hash_a" : "b54d09218e0d6efc964b78b070620a1fa19c7e069672b4c6313cee2c9b0623f2",
#      "hash_b" : "bbaa9876dab238dcf5799bfd8319ed0bab805e844f45cf0de33f40697b11a845",
#      "relationship" : 4,
#      "do_default_content_merge" : true,
#      "delete_b" : true
#    }
#}

    def dedupe(self, original_hash="", upscaled_hash=""):
        client = get_hydrus_client()
        time.sleep(5)
        print("Orig: {}".format(original_hash))
        print("Upscale: {}".format(upscaled_hash))
        body = [
            {
                "hash_a": original_hash,
                "hash_b": upscaled_hash,
                "relationship": 4,
                "do_default_content_merge": True
            }
        ]
        print("Body: {}".format(body))

        results = client.set_file_relationships(body)
        return results

class HydrusImport:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
                    "required": {
                        "images": ("IMAGE", {"forceInput": True}, ),
                    },
                    "optional": {
                        "positive": ("STRING",{ "multiline": True, "forceInput": True}, ),
                        "negative": ("STRING",{"multiline": True, "forceInput": True}, ),
                        "modelname": ("STRING",{"default": '', "multiline": False, "forceInput": True},),
                        "seed": ("STRING",{"default": '', "multiline": False, "forceInput": False},),
                        "loras": ("STRING",{"default": "", "forceInput": False},),
                        "tags": ("STRING",{"default": "ai, comfyui, hyshare: ai", "forceInput": True},),
                        "dedupe": ("BOOLEAN", {"default": False},),
                    },
                    "hidden": {
                        "prompt": "PROMPT",
                        "extra_pnginfo": "EXTRA_PNGINFO",
                    },
                }

    RETURN_TYPES = ["STRING"]
    RETURN_NAMES = ["upscale_hash"]
    FUNCTION = "import_to_hydrus"
    
    #OUTPUT_IS_LIST = (True,)
    OUTPUT_NODE = True

    CATEGORY = "image"
    # I had this in Hydrus originally, honestly smarter to just have it alongside the other image savers

    def import_to_hydrus(self, images, positive="", negative="", modelname="", seed="", loras="", tags="", dedupe=False, prompt=None, extra_pnginfo=None):
        client = get_hydrus_client()
        imagelist = []
        split = tags.split(',')
        meta = []
        # I'm sure there's a better way to do this, but I'm a manager now so I have become a bad programmer
        if positive != "":
            meta.append('positive: {}'.format(positive))
        if negative != "":
            meta.append('negative: {}'.format(negative))
        if modelname != "":
            meta.append('modelname: {}'.format(modelname))
        if loras != "":
            for lora in loras:
                meta.append('lora: {}'.format(lora))
        if seed != "":
            meta.append('seed: {}'.format(seed))

        metatags = meta + split
        
        for index, image in enumerate(images):
            # From this line down to metadata.add_text is shamelessly stolen from the wlsh save with metadata node
            image_quantity = len(images)
            # Programmer things. Indicies start at 0, but "importing 0 out of n) doesnt make sense
            image_index = index + 1
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
            imagefile = TemporaryFile()
            img.save(imagefile, "PNG", comment=comment, pnginfo=metadata, optimize=True)
            # File gets saved, and the temp file requires seeking to "reset" back to the start of file
            imagefile.seek(0)
            print("{} Importing Image {} out of {}...".format(hydrus_logging_prefix, image_index, image_quantity))
            self.import_image(imagefile, client, metatags)
            # After import, the file (yet again) is read, so needs to be reset
            imagefile.seek(0)
            hash = hashlib.sha256(imagefile.read()).hexdigest()
            if dedupe:
                #Deduplication should only occur with one image because I'm cringe and don't know what I'm doing
                return hash
        # This doesn't return a preview of the image, I'm not sure wtf I'm doing wrong. Maybe it needs to be the img, w/e idk
        return imagelist


    def add_and_tag(self, client, image, tags, tag_service_key):
        hash = ""
        result = client.add_file(image)
        # How is the file service chosen? Trick question, it's default!
        # TODO: let the file service(s) be an input
        if result["status"] != ImportStatus.FAILED:
            hash = result["hash"]
        client.add_tags(hashes=[hash], service_keys_to_tags={tag_service_key: tags})
        print("{} Done!".format(hydrus_logging_prefix))
        return result

    def import_image(self, image, client, tags=None):
        if not hydrus_api.utils.verify_permissions(client, REQUIRED_PERMISSIONS):
            print("{} The API key does not grant all required permissions: {}".format(hydrus_logging_prefix, REQUIRED_PERMISSIONS))
            return 404
        tag_service_key = get_hydrus_service_key(client)
        result = self.add_and_tag(client, image, tags, tag_service_key)
        return result

NODE_CLASS_MAPPINGS = {
    #IO
    "Hydrus Image Importer": HydrusImport,
    "Hydrus Image Exporter": HydrusExport,
    "Hydrus Image Dedupe": HydrusDuplicates
}
