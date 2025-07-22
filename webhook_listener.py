from fastapi import FastAPI, Request, Header, HTTPException
import hmac
import hashlib
import subprocess

app = FastAPI()

SECRET = b'your_secret'  # Hardcoded GitHub webhook secret

def verify_signature(payload: bytes, signature: str) -> bool:
    mac = hmac.new(SECRET, msg=payload, digestmod=hashlib.sha256)
    expected_signature = "sha256=" + mac.hexdigest()
    return hmac.compare_digest(expected_signature, signature)

@app.post("/webhook")
async def webhook(
    request: Request,
    x_hub_signature_256: str = Header(None),
    x_github_event: str = Header(None)
):
    body = await request.body()

    if not x_hub_signature_256 or not verify_signature(body, x_hub_signature_256):
        raise HTTPException(status_code=403, detail="Invalid signature")

    if x_github_event == "push":
        subprocess.Popen(["/bin/bash", "./deploy.sh"])
        return {"message": "Deployment started"}

    return {"message": "Ignored"}

