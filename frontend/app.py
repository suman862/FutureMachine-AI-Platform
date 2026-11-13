import io
import gradio as gr
import requests
from PIL import Image

GATEWAY_URL = "http://gateway:8000"

def process_vision(image: Image.Image, prompt: str):
    if image is None:
        return "Please provide an image."
    
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='JPEG')
    img_byte_arr = img_byte_arr.getvalue()
    
    files = {"file": ("image.jpg", img_byte_arr, "image/jpeg")}
    data = {"prompt": prompt}
    
    try:
        response = requests.post(f"{GATEWAY_URL}/v1/vision", files=files, data=data, timeout=60)
        if response.status_code == 200:
            return response.json().get("text", "No response text found.")
        return f"Error {response.status_code}: {response.text}"
    except Exception as exc:
        return f"Gateway connection failed: {exc}"

def process_audio(audio_path: str):
    if audio_path is None:
        return "Please record or upload an audio file."
    
    try:
        with open(audio_path, "rb") as f:
            files = {"file": ("audio.wav", f, "audio/wav")}
            response = requests.post(f"{GATEWAY_URL}/v1/audio", files=files, timeout=60)
            
        if response.status_code == 200:
            res = response.json()
            return f"**Language:** {res.get('language')} (Prob: {res.get('language_probability'):.2f})\n\n**Transcription:**\n{res.get('text')}"
        return f"Error {response.status_code}: {response.text}"
    except Exception as exc:
        return f"Gateway connection failed: {exc}"

def process_text(prompt: str, max_tokens: int, temperature: float):
    if not prompt.strip():
        return "Please enter a prompt."
    
    payload = {
        "prompt": prompt,
        "max_tokens": int(max_tokens),
        "temperature": float(temperature)
    }
    
    try:
        response = requests.post(f"{GATEWAY_URL}/v1/text", json=payload, timeout=60)
        if response.status_code == 200:
            return response.json().get("text", "No response text found.")
        return f"Error {response.status_code}: {response.text}"
    except Exception as exc:
        return f"Gateway connection failed: {exc}"

# Build the UI
with gr.Blocks(title="Multimodal AI Studio") as demo:
    gr.Markdown("#  Multimodal AI Studio")
    gr.Markdown("A unified inference interface for intelligent AI applications.")
    
    with gr.Tabs():
        with gr.TabItem("Text (Qwen)"):
            with gr.Row():
                with gr.Column():
                    t_prompt = gr.Textbox(value="Explain quantum computing in simple terms.", label="Prompt", lines=4)
                    t_max_tokens = gr.Slider(minimum=16, maximum=512, value=128, step=16, label="Max Tokens")
                    t_temp = gr.Slider(minimum=0.0, maximum=1.0, value=0.7, step=0.05, label="Temperature")
                    t_btn = gr.Button("Generate Text", variant="primary")
                with gr.Column():
                    t_output = gr.Textbox(label="Model Response", lines=12)
            t_btn.click(process_text, inputs=[t_prompt, t_max_tokens, t_temp], outputs=t_output)

        with gr.TabItem("Vision (SmolVLM)"):
            with gr.Row():
                with gr.Column():
                    v_input = gr.Image(type="pil", label="Upload Image (Max 10 MB)")
                    v_prompt = gr.Textbox(value="Describe this image in detail.", label="Inference Prompt")
                    v_btn = gr.Button("Run Vision Inference", variant="primary")
                with gr.Column():
                    v_output = gr.Textbox(label="Model Output", lines=10)
            v_btn.click(process_vision, inputs=[v_input, v_prompt], outputs=v_output)
            
        with gr.TabItem("Audio (Whisper)"):
            with gr.Row():
                with gr.Column():
                    a_input = gr.Audio(type="filepath", label="Record or Upload Audio (Max 25 MB)")
                    a_btn = gr.Button("Transcribe Audio", variant="primary")
                with gr.Column():
                    a_output = gr.Markdown(label="Transcription Result")
            a_btn.click(process_audio, inputs=[a_input], outputs=a_output)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False)