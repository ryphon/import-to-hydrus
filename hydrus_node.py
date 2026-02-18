"""
ComfyUI custom nodes for importing/exporting images from Hydrus.
Handles tagging, metadata, and image management via the Hydrus API.
"""

import os
import json
import time
import hashlib
import logging
from datetime import datetime
from tempfile import TemporaryFile

import numpy as np
import torch
from PIL import Image, PngInfo
import hydrus_api
import hydrus_api.utils
from hydrus_api import ImportStatus

from comfy import sd
import folder_paths

# Configuration
REQUIRED_PERMISSIONS = (hydrus_api.Permission.IMPORT_FILES, hydrus_api.Permission.ADD_TAGS)
HYDRUS_KEY = os.environ.get("HYDRUS_KEY")
HYDRUS_URL = os.environ.get("HYDRUS_URL")
HYDRUS_API_FILE = "hydrus_api.txt"
DEFAULT_TAG_SERVICE = "my tags"
DUPLICATE_RELATIONSHIP_TYPE = 4  # Hydrus API: 4 = upscaled/alternative

logger = logging.getLogger("hydrus_node")
logger.setLevel(logging.DEBUG)

def get_timestamp(time_format="%Y-%m-%d-%H%M%S"):
    """Generate a timestamp string."""
    try:
        return datetime.now().strftime(time_format)
    except ValueError:
        # Fall back to default format if custom format is invalid
        return datetime.now().strftime("%Y-%m-%d-%H%M%S")


def get_hydrus_service_key(client):
    """
    Get the service key for the 'my tags' tag service.
    
    Returns:
        str: The service key, or empty string if not found.
    """
    local_tags = client.get_services().get('local_tags', [])
    for service in local_tags:
        if service['name'] == DEFAULT_TAG_SERVICE:
            return service['service_key']
    return ""


def _load_api_credentials_from_file():
    """
    Load Hydrus API credentials from hydrus_api.txt file.
    
    Returns:
        tuple: (api_key, api_url) or (None, None) if file not found/invalid
    """
    try:
        dir_path = os.path.dirname(os.path.realpath(__file__))
        filepath = os.path.join(dir_path, HYDRUS_API_FILE)
        
        if not os.path.exists(filepath):
            return None, None
            
        with open(filepath, "r") as f:
            api_config = json.loads(f.read())
            return api_config.get('hydrus_key'), api_config.get('hydrus_url')
    except (json.JSONDecodeError, IOError, FileNotFoundError) as e:
        logger.debug(f"Could not load credentials from file: {e}")
        return None, None


def get_hydrus_client():
    """
    Create a Hydrus API client from environment variables or config file.
    
    Returns:
        hydrus_api.Client: Authenticated Hydrus client
        
    Raises:
        ValueError: If no valid credentials are found
    """
    api_key = HYDRUS_KEY
    api_url = HYDRUS_URL
    
    # Try loading from file if env vars not set
    if not api_key or not api_url:
        file_key, file_url = _load_api_credentials_from_file()
        api_key = api_key or file_key
        api_url = api_url or file_url
    
    if not api_key or not api_url:
        raise ValueError(
            f"Hydrus API credentials required. Set HYDRUS_KEY and HYDRUS_URL "
            f"environment variables, or create {HYDRUS_API_FILE} with credentials."
        )
    
    return hydrus_api.Client(api_key, api_url)

class HydrusExport:
    """ComfyUI node for exporting/querying images from Hydrus."""

    def __init__(self):
        self.client = get_hydrus_client()

    @classmethod
    def INPUT_TYPES(cls):
        input_dir = folder_paths.get_input_directory()
        files = [f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))]
        return {
            "required": {},
            "optional": {
                "images": (sorted(files), {"image_upload": False}),
                "tag": ("STRING", {"default": '', "multiline": False, "forceInput": True}),
                "hash": ("STRING", {"default": '', "multiline": False, "forceInput": True}),
                "usetag": ("BOOLEAN", {"default": False}),
                "usehash": ("BOOLEAN", {"default": False}),
            },
            "hidden": {},
        }

    RETURN_TYPES = ["IMAGE", "MODEL", "CLIP", "VAE", "STRING", "STRING", "STRING", "STRING", "STRING"]
    RETURN_NAMES = ["image", "model", "clip", "vae", "positive", "negative", "modelname", "seed", "loras"]
    FUNCTION = "export_from_hydrus"
    OUTPUT_NODE = False
    CATEGORY = "image"

    def get_files_with_tag(self, tag):
        """Get list of file hashes matching a tag."""
        file_ids = self.client.search_files([tag])['file_ids']
        files_metadata = self.client.get_file_metadata(file_ids=file_ids)['metadata']
        return [file_meta['hash'] for file_meta in files_metadata]

    def get_file_metadata(self, hash_val):
        """Extract metadata tags from a file."""
        metadata = self.client.get_file_metadata(hashes={hash_val})['metadata'][0]
        tag_service = get_hydrus_service_key(self.client)
        tags = metadata['tags'][tag_service]['display_tags']['0']
        
        outputs = {'loras': []}
        tag_prefix_map = {
            'modelname:': 'modelname',
            'positive:': 'positive',
            'negative:': 'negative',
            'seed:': 'seed',
            'lora:': 'loras',
        }
        
        for tag_text in tags:
            for prefix, key in tag_prefix_map.items():
                if tag_text.startswith(prefix):
                    value = tag_text.replace(prefix, '')
                    if key == 'loras':
                        outputs[key].append(value)
                    else:
                        outputs[key] = value
                    break
        
        return outputs

    def get_file(self, hash_val):
        """Download file content from Hydrus."""
        return self.client.get_file(hash_val).content

    def checkpointer(self, ckpt_name=""):
        """Load a checkpoint and return model components."""
        ckpt_path = folder_paths.get_full_path('checkpoints', ckpt_name)
        model, clip, vae, _ = sd.load_checkpoint_guess_config(
            ckpt_path, output_vae=True, output_clip=True
        )
        return model, clip, vae

    def prep_image(self, hash_val):
        """Prepare image and metadata from Hydrus for use in ComfyUI."""
        tags = self.get_file_metadata(hash_val)
        model_name = f"{tags.get('modelname', '')}.safetensors"
        model, clip, vae = self.checkpointer(model_name)
        
        # Load image from Hydrus
        hydrus_file_data = self.get_file(hash_val)
        with TemporaryFile() as hydrus_file:
            hydrus_file.write(hydrus_file_data)
            hydrus_file.seek(0)
            img = Image.open(hydrus_file).convert("RGB")
        
        # Convert to tensor
        image_array = np.array(img).astype(np.float32) / 255.0
        image_tensor = torch.from_numpy(image_array)[None,]
        
        # Return in ComfyUI format
        return (
            image_tensor,
            model,
            clip,
            vae,
            tags.get('positive', ''),
            tags.get('negative', ''),
            tags.get('modelname', ''),
            tags.get('seed', ''),
            tags.get('loras', []),
        )

    def export_from_hydrus(self, images="", tag="", hash_val="", usehash=False, usetag=False):
        """Main export function - load image from Hydrus by hash or tag."""
        if usetag:
            hash_list = self.get_files_with_tag(tag)
            if not hash_list:
                raise ValueError(f"No files found with tag: {tag}")
            hash_val = hash_list[0]
        elif usehash:
            if not hash_val:
                raise ValueError("Hash required when usehash is True")
        else:
            # Load from file
            image_path = folder_paths.get_annotated_filepath(images, './')
            logger.debug(f"Loading image: {images}")
            with open(image_path, 'rb') as file:
                hash_val = hashlib.sha256(file.read()).hexdigest()
        
        return self.prep_image(hash_val)

class HydrusDuplicates:
    """ComfyUI node for marking files as duplicates in Hydrus."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "original_hash": ("STRING", {"multiline": True, "forceInput": True}),
                "upscaled_hash": ("STRING", {"multiline": True, "forceInput": True}),
            },
            "optional": {},
            "hidden": {},
        }

    RETURN_TYPES = []
    FUNCTION = "dedupe"
    OUTPUT_NODE = True
    CATEGORY = "image"

    def dedupe(self, original_hash="", upscaled_hash=""):
        """Mark two files as duplicates in Hydrus."""
        client = get_hydrus_client()
        
        # Give Hydrus a moment to process the previous import
        time.sleep(5)
        
        logger.debug(f"Original: {original_hash}")
        logger.debug(f"Upscaled: {upscaled_hash}")
        
        body = [
            {
                "hash_a": original_hash,
                "hash_b": upscaled_hash,
                "relationship": DUPLICATE_RELATIONSHIP_TYPE,
                "do_default_content_merge": True,
            }
        ]
        
        logger.debug(f"Sending dedup request: {body}")
        return client.set_file_relationships(body)

class HydrusImport:
    """ComfyUI node for importing images to Hydrus with metadata tags."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE", {"forceInput": True}),
            },
            "optional": {
                "positive": ("STRING", {"multiline": True, "forceInput": True}),
                "negative": ("STRING", {"multiline": True, "forceInput": True}),
                "modelname": ("STRING", {"default": '', "multiline": False, "forceInput": True}),
                "seed": ("STRING", {"default": '', "multiline": False, "forceInput": False}),
                "loras": ("STRING", {"default": "", "forceInput": False}),
                "tags": ("STRING", {"default": "ai, comfyui, hyshare: ai", "forceInput": True}),
                "dedupe": ("BOOLEAN", {"default": False}),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    RETURN_TYPES = ["STRING"]
    RETURN_NAMES = ["upscale_hash"]
    FUNCTION = "import_to_hydrus"
    OUTPUT_NODE = True
    CATEGORY = "image"

    def _build_metadata_tags(self, positive, negative, modelname, seed, loras, tags):
        """Build list of all tags to apply to imported file."""
        meta = []
        
        # Add generation metadata as tags
        if positive:
            meta.append(f'positive: {positive}')
        if negative:
            meta.append(f'negative: {negative}')
        if modelname:
            meta.append(f'modelname: {modelname}')
        if seed:
            meta.append(f'seed: {seed}')
        
        # Add lora tags
        if loras:
            lora_list = loras if isinstance(loras, list) else [loras]
            for lora in lora_list:
                meta.append(f'lora: {lora}')
        
        # Add user-provided tags
        user_tags = [tag.strip() for tag in tags.split(',')]
        meta.extend(user_tags)
        
        return meta

    def _image_to_tensor(self, image_array):
        """Convert PIL image to torch tensor."""
        i = 255.0 * image_array.cpu().numpy()
        img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))
        return img

    def _save_image_with_metadata(self, pil_image, prompt, extra_pnginfo):
        """Save image with PNG metadata and return as bytes."""
        metadata = PngInfo()
        
        if prompt:
            metadata.add_text("prompt", json.dumps(prompt))
        if extra_pnginfo:
            for key, value in extra_pnginfo.items():
                metadata.add_text(key, json.dumps(value))
        
        imagefile = TemporaryFile()
        pil_image.save(imagefile, "PNG", pnginfo=metadata, optimize=True)
        imagefile.seek(0)
        return imagefile

    def add_and_tag(self, client, image_file, tags, tag_service_key):
        """Add file to Hydrus and apply tags."""
        result = client.add_file(image_file)
        
        if result["status"] != ImportStatus.FAILED:
            hash_val = result["hash"]
            client.add_tags(
                hashes=[hash_val],
                service_keys_to_tags={tag_service_key: tags}
            )
            logger.debug("Import successful")
        else:
            logger.error(f"Import failed: {result}")
        
        return result

    def import_image(self, image_file, client, tags=None):
        """Import single image to Hydrus with tags."""
        if not hydrus_api.utils.verify_permissions(client, REQUIRED_PERMISSIONS):
            raise PermissionError(
                f"API key missing required permissions: {REQUIRED_PERMISSIONS}"
            )
        
        tag_service_key = get_hydrus_service_key(client)
        return self.add_and_tag(client, image_file, tags, tag_service_key)

    def import_to_hydrus(
        self, images, positive="", negative="", modelname="", seed="", loras="",
        tags="", dedupe=False, prompt=None, extra_pnginfo=None
    ):
        """Import image batch to Hydrus."""
        client = get_hydrus_client()
        
        # Build metadata tags
        metatags = self._build_metadata_tags(positive, negative, modelname, seed, loras, tags)
        
        last_hash = None
        
        for index, image in enumerate(images):
            image_count = len(images)
            image_num = index + 1
            
            logger.debug(f"Importing image {image_num} of {image_count}...")
            
            # Convert tensor to PIL image
            pil_image = self._image_to_tensor(image)
            
            # Save with metadata
            imagefile = self._save_image_with_metadata(pil_image, prompt, extra_pnginfo)
            
            # Import to Hydrus
            self.import_image(imagefile, client, metatags)
            
            # Calculate hash for deduplication
            imagefile.seek(0)
            last_hash = hashlib.sha256(imagefile.read()).hexdigest()
            imagefile.close()
        
        # Return the last imported file's hash for potential deduplication
        return last_hash if last_hash else ""

NODE_CLASS_MAPPINGS = {
    "Hydrus Image Importer": HydrusImport,
    "Hydrus Image Exporter": HydrusExport,
    "Hydrus Image Dedupe": HydrusDuplicates,
}
NODE_CLASS_DISPLAY_NAMES = {
    "Hydrus Image Importer": "Hydrus Image Importer",
    "Hydrus Image Exporter": "Hydrus Image Exporter",
    "Hydrus Image Dedupe": "Hydrus Image Dedupe",
}
