from .fireworks_provider import FireworksProvider
from .email_notifier import send_model_api_finished

def check_and_notify():
    provider = FireworksProvider()
    text = provider.chat([
        {"role": "system", "content": "Reply with exactly MODEL_API_OK."},
        {"role": "user", "content": "Health check"}
    ], temperature=0, max_tokens=10)
    if "MODEL_API_OK" not in text:
        raise RuntimeError(f"Unexpected model health response: {text!r}")
    send_model_api_finished(
        "Job Hunter: Model API finished",
        "Fireworks model API health check passed. The model layer is ready for the Job Hunter pipeline."
    )
    return True
