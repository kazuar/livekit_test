from diffusers import AutoPipelineForImage2Image
from diffusers.utils import load_image
import torch

pipe = AutoPipelineForImage2Image.from_pretrained(
    "stabilityai/sdxl-turbo", 
    torch_dtype=torch.float16, 
    variant="fp16",
    use_safetensors=True
)
pipe.to("cuda")

init_image = load_image("https://huggingface.co/datasets/huggingface/documentation-images/resolve/main/diffusers/cat.png").resize((512, 512))

init_image = load_image("/home/ivid/projs/livekit_test/test_images/test_input.png").resize((512, 512))

prompt = "cat wizard, gandalf, lord of the rings, detailed, fantasy, cute, adorable, Pixar, Disney, 8k"

# prompt = "add words to the image"

image = pipe(
    prompt, 
    image=init_image, 
    num_inference_steps=10,
    strength=1.0, 
    guidance_scale=0.0,
    output_type="pil"
).images[0]
image.save("output.png")
