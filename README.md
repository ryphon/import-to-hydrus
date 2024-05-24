wip, should be mostly functional, but doesn't come with any assurances or garuntees.

set HYDRUS_KEY and HYDRUS_URL in your environment before you start Comfy, or fill in the file in the projects repo with your hydrus servers information

attach all the relevant prompts.

i've found that wlsh nodes export a LOT of the data you'd want to inject in

rgthree nodes do a great job to organize things

crystools also have some very good pipe nodes to move the data along to the end of the workflow cleanly

some time in the next few days ill go rebuild a simple workflow with saving to hydrus set up with vanilla comfy

your hydrus api token probably needs import files and add tags

your hydrus server needs to be accessible from the system running comfyui. be sure that your dns is set intelligently/accordingly as well

the tags object takes a comma separated list of tags. if you want namespaces, just put them in

example tags, `ai, comfyui, hyshare: ai`

all the inputs except image are optional, you'll just end up with very limited tags on the image

the node by default saves a ton of metadata to the png that gets created, i have a lot of storage so i just don't care

if i think of more i'll write it down, and find some time in the next few days to format correctly
