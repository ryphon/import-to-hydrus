from datetime import datetime
import json
import hydrus_api
import hydrus_api.utils
import numpy as np
from PIL.PngImagePlugin import PngInfo

REQUIRED_PERMISSIONS = (hydrus_api.Permission.IMPORT_FILES, hydrus_api.Permission.ADD_TAGS)

# image I/O
def get_timestamp(time_format="%Y-%m-%d-%H%M%S"):
    now = datetime.now()
    try:
        timestamp = now.strftime(time_format)
    except:
        timestamp = now.strftime("%Y-%m-%d-%H%M%S")

    return(timestamp)

def make_filename(filename="ComfyUI", seed={"seed":0}, modelname="sd", counter=0, time_format="%Y-%m-%d-%H%M%S"):
    '''
    Builds a filename by reading in a filename format and returning a formatted string using input tokens
    Tokens:
    %time - timestamp using the time_format value
    %model - modelname using the modelname input
    %seed - seed from the seed input
    %counter - counter integer from the counter input
    '''
    timestamp = get_timestamp(time_format)

    # parse input string
    filename = filename.replace("%time",timestamp)
    filename = filename.replace("%model",modelname)
    filename = filename.replace("%seed",str(seed))
    filename = filename.replace("%counter",str(counter))  

    if filename == "":
        filename = timestamp
    return(filename)  

def make_tags(positive, negative, modelname="unknown", seed=-1, info=None):
    tags = {}
    tags['positive'] = positive
    tags['negative'] = negative
    tags['modelname'] = modelname
    tags['seed'] = seed
    tags['info'] = info
    return tags

def make_comment(positive, negative, modelname="unknown", seed=-1, info=None):
    comment = ""
    if(info is None):
        comment = "Positive prompt:\n" + positive + "\nNegative prompt:\n" + negative + "\nModel: " + modelname + "\nSeed: " + str(seed)
        return comment
    else:
        # reformat to stop long precision
        try:
            info['CFG scale: '] = "{:.2f}".format(info['CFG scale: '])
        except:
            pass
        try:
            info['Denoising strength: '] = "{:.2f}".format(info['Denoising strength: '])
        except:
            pass

        comment = "Positive prompt:\n" + positive + "\nNegative prompt:\n" + negative + "\nModel: " + modelname
        for key in info:
            newline = "\n" + key + str(info[key])
            comment += newline
    # print(comment)
    return comment


class Hydrus:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
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
                        "prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"
                    },
                }

    RETURN_TYPES = ()
    FUNCTION = "save_images"

    OUTPUT_NODE = True

    CATEGORY = "Hydrus/"


    def import_path(self, client: hydrus_api.Client, tags, file, tag_service_keys="my tags"):
        hydrus_api.utils.add_and_tag_files(client, (file,), tags, tag_service_keys)
    
    
    def import_image(self, image, metadata):
        api_url = "
        api_key = "
        client = hydrus_api.Client(api_key, api_url)
        if not hydrus_api.utils.verify_permissions(client, REQUIRED_PERMISSIONS):
            print("The API key does not grant all required permissions:", REQUIRED_PERMISSIONS)
            return 404
        tag_service_keys = "my tags"
        positive = metadata['positive']
        negative = metadata['negative']
        modelname = metadata['modelname']
        seed = metadata['seed']
        info = metadata['info']
        make_tags(positive, negative, modelname, seed, info)
        # Translate passed tag-service keys or names into keys. If there are multiple services with the same name we just
        # take the first one
        #service_mapping = hydrus_api.utils.get_service_mapping(client)
        print(f"Importing image to Hydrus")
        import_path(client, tags, image, tag_service_keys)
    
        return 404

    def save_images(self, images, filename_prefix="ComfyUI", comment="", extension='png', quality=100, prompt=None, extra_pnginfo=None):
        imgCount = 1
        paths = list()
        for image in images:
            i = 255. * image.cpu().numpy()
            img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))
            metadata = PngInfo()
            
            if prompt is not None:
                metadata.add_text("prompt", json.dumps(prompt))
            if extra_pnginfo is not None:
                for x in extra_pnginfo:
                    metadata.add_text(x, json.dumps(extra_pnginfo[x]))
            metadata.add_text("parameters", comment)
            metadata.add_text("comment", comment)
            if(images.size()[0] > 1):
                filename_prefix += "_{:02d}".format(imgCount)

            file = f"{filename_prefix}.{extension}"
            if extension == 'png':
                # print(comment)
                #img.save(os.path.join(output_path, file), comment=comment, pnginfo=metadata, optimize=True)
                self.import_image(file, metadata)
            else:
                #img.save(os.path.join(output_path, file))
                self.import_image(file, metadata)

NODE_CLASS_MAPPINGS = {
    #IO
    "Hydrus Image Importer": Hydrus,
}
