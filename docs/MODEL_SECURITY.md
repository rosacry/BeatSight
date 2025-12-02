# BeatSight Model Security & Protection

## Overview

This document describes the multi-layered security system that provides **ABSOLUTE** protection against model theft for BeatSight's ML models.

**Key Principle: The model NEVER leaves our servers. Users only interact via API.**

---

## 🛡️ Defense Layers

### Layer 1: Architecture Isolation (FUNDAMENTAL)

The most important protection: **models only exist on Modal servers**.

```
┌─────────────────────────────────────────────────────────────────────┐
│                          USER SIDE                                   │
│  ┌─────────────┐    ┌──────────────┐    ┌─────────────────────────┐ │
│  │  Frontend   │───▶│   Backend    │───▶│  API (predictions only) │ │
│  │  (Web/App)  │    │   (FastAPI)  │    │  No model weights ever  │ │
│  └─────────────┘    └──────────────┘    └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        MODAL SERVERS (GPU)                          │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │  Encrypted Model Volume                                          ││
│  │  ┌───────────────────┐                                          ││
│  │  │ production_v5.enc │──┐                                       ││
│  │  └───────────────────┘  │                                       ││
│  └─────────────────────────┼───────────────────────────────────────┘│
│                            │                                         │
│  ┌─────────────────────────▼───────────────────────────────────────┐│
│  │  GPU Worker (Ephemeral Container)                                ││
│  │                                                                   ││
│  │  1. Decrypt model in memory (key from Modal secrets)            ││
│  │  2. Run inference                                                ││
│  │  3. Return predictions ONLY                                      ││
│  │  4. Container destroyed (model memory cleared)                   ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
```

**What users get:** Beatmap predictions (JSON with timing data)
**What users DON'T get:** Model weights, architecture details, inference code

---

### Layer 2: Encrypted Storage at Rest

Models are encrypted with **AES-256-GCM** before upload to Modal volume.

```python
# Encrypt locally BEFORE uploading to Modal
from training.inference.model_protection import ModelEncryptor

encryptor = ModelEncryptor()
encryptor.encrypt_file(
    "models/production_v5.pth",    # Plain checkpoint
    "models/production_v5.enc",     # Encrypted output
    key="your-secret-key",           # From password manager
    obfuscate=True,                  # Also obfuscate layer names
)

# Upload ONLY the encrypted file to Modal
modal volume put beatsight-models models/production_v5.enc
```

**Security properties:**
- AES-256-GCM: Authenticated encryption (confidentiality + integrity)
- PBKDF2-SHA256: 600,000 iterations for key derivation (OWASP 2023)
- Random salt + nonce per encryption
- Checksum verification on decryption

---

### Layer 3: Secure Runtime Decryption

Models are decrypted **only in memory** on GPU workers.

```python
# In Modal worker (production)
from training.inference.model_protection import SecureModelLoader

loader = SecureModelLoader()  # Key from MODEL_ENCRYPTION_KEY env var

# Decrypts directly to memory - NEVER writes to disk
model = loader.load_model(
    "/models/production_v5.enc",
    model_class=DrumClassifierV5,
    model_kwargs=config,
)

# After inference, container is destroyed and memory is cleared
```

**Key is stored in Modal Secrets**, never in code:
```bash
# Set up Modal secret (one-time)
modal secret create beatsight-model-keys \
    MODEL_ENCRYPTION_KEY="your-super-secret-key" \
    WATERMARK_KEY="your-watermark-key"
```

---

### Layer 4: Model Obfuscation

Even if encrypted files were somehow obtained, reverse-engineering is difficult:

- **Key obfuscation**: State dict keys are hashed (SHA-256)
- **Layer names hidden**: `conv1.weight` → `a4f2b8c1d3e5f6a7`
- **Requires key map**: Only stored inside encrypted file

```python
# Original checkpoint keys:
{
    "conv1.weight": tensor(...),
    "conv2.weight": tensor(...),
}

# After obfuscation:
{
    "a4f2b8c1d3e5f6a7": tensor(...),  # Hashed key
    "9c8b7a6f5e4d3c2b": tensor(...),
    "__key_map__": {...},  # For deobfuscation (encrypted)
}
```

---

### Layer 5: Model Watermarking (Provenance)

Invisible watermarks are embedded in model weights:

```python
from training.inference.model_protection import ModelWatermarker

watermarker = ModelWatermarker(watermark_key="secret-watermark-key")

# Embed watermark before encryption
watermarked_state = watermarker.embed_watermark(
    state_dict=model.state_dict(),
    owner_id="BeatSight",
    model_version="production-v5-2025",
)

# Later: Verify if a model is yours
is_ours, confidence = watermarker.verify_watermark(
    state_dict=suspicious_model.state_dict(),
    owner_id="BeatSight",
    model_version="production-v5-2025",
)
print(f"Watermark match: {is_ours} ({confidence:.1%} confidence)")
```

**If a model is leaked:**
1. We can prove ownership in court
2. We can identify which version was leaked
3. We can trace the source if different watermarks per customer

---

### Layer 6: Access Control & Anomaly Detection

Backend monitors for model extraction attacks:

- **Rate limiting**: Max 30 requests/minute per user
- **Input uniqueness monitoring**: Extraction attacks use many unique inputs
- **Boundary probing detection**: Unusual input distributions
- **Automated blocking**: Suspicious accounts flagged

---

## 🔑 Key Management

### Encryption Key Setup

1. **Generate a strong key:**
   ```bash
   # 256-bit key
   openssl rand -base64 32
   ```

2. **Store in Modal Secrets:**
   ```bash
   modal secret create beatsight-model-keys \
       MODEL_ENCRYPTION_KEY="<your-key>" \
       WATERMARK_KEY="<your-watermark-key>"
   ```

3. **Store backup in secure password manager** (1Password, Bitwarden, etc.)

4. **NEVER commit keys to git**

### Key Rotation

To rotate keys:
1. Decrypt model with old key
2. Re-encrypt with new key
3. Update Modal secret
4. Deploy updated encrypted file

---

## 🚀 Deployment Workflow

### Initial Setup (One-time)

```bash
# 1. Train model on Lambda Labs
# ... training on Lambda Labs A100 ...

# 2. Download final checkpoint locally
scp ubuntu@lambda:~/BeatSight/runs/best_model.pth ./models/

# 3. Watermark the model
python -c "
from training.inference.model_protection import ModelWatermarker
import torch

checkpoint = torch.load('models/best_model.pth', map_location='cpu')
watermarker = ModelWatermarker('your-watermark-key')
checkpoint['model_state_dict'] = watermarker.embed_watermark(
    checkpoint['model_state_dict'],
    owner_id='BeatSight',
    model_version='production-v5-2025',
)
torch.save(checkpoint, 'models/watermarked_model.pth')
"

# 4. Encrypt the model
python -m training.inference.model_protection encrypt \
    models/watermarked_model.pth \
    models/production_v5.enc \
    --model-id "production-v5-2025"

# 5. Upload to Modal volume
modal volume put beatsight-models models/production_v5.enc

# 6. Delete local plain checkpoints
rm models/best_model.pth models/watermarked_model.pth

# 7. Deploy to Modal
modal deploy modal_app.py
```

### Model Updates

```bash
# 1. Train new model
# 2. Watermark and encrypt (steps 3-4 above)
# 3. Upload with new name
modal volume put beatsight-models models/production_v6.enc

# 4. Update code to use new model
# 5. Deploy
modal deploy modal_app.py
```

---

## ❓ FAQ

### Q: Can Modal employees see my model?
**A:** Modal does not have access to your model encryption key (stored in Modal Secrets which are encrypted). Even if they accessed the volume, they'd only see encrypted bytes.

### Q: What if someone reverse-engineers the inference API?
**A:** They'd only learn what inputs and outputs look like, not the model weights. Model extraction attacks (learning a model from API queries) are:
- Extremely expensive (millions of queries)
- Detectable by our anomaly detection
- Would produce an inferior approximation

### Q: What if my encryption key is leaked?
**A:** 
1. Immediately rotate the key
2. Re-encrypt all models with new key
3. Revoke any API tokens that might be compromised

### Q: Can someone steal the model from GPU memory?
**A:**
- Modal containers are isolated and ephemeral
- No SSH access to GPU workers
- Memory is cleared after container destruction
- Would require physical access to Modal's data center

### Q: What about during training on Lambda Labs?
**A:**
- Training is done on temporary Lambda instances
- Checkpoints are uploaded to S3 (private bucket)
- Instance is terminated after training
- Final model is watermarked and encrypted before production

---

## 📋 Security Checklist

Before deploying a new model:

- [ ] Model trained on private Lambda Labs instance
- [ ] Watermark embedded with unique owner/version ID
- [ ] Model encrypted with AES-256-GCM
- [ ] Encryption key stored in Modal Secrets
- [ ] Plain checkpoint files deleted from local machine
- [ ] Encrypted file uploaded to Modal volume
- [ ] `.gitignore` includes all checkpoint patterns
- [ ] Rate limiting configured in backend
- [ ] Anomaly detection monitoring enabled

---

## 🛠️ Tools Reference

### Encrypt a model
```bash
python -m training.inference.model_protection encrypt input.pth output.enc
```

### Verify encryption
```bash
python -m training.inference.model_protection verify encrypted.enc
```

### Decrypt (testing only, NEVER in production)
```bash
python -m training.inference.model_protection decrypt encrypted.enc output.pth
```

---

## 🔒 Summary

| Layer | Protection | Against |
|-------|------------|---------|
| 1. Architecture | API-only access | Direct model access |
| 2. Encryption | AES-256-GCM | Stolen files |
| 3. Memory-only | No disk writes | Container inspection |
| 4. Obfuscation | Hashed keys | Reverse engineering |
| 5. Watermarks | Ownership proof | Disputed leaks |
| 6. Monitoring | Rate limits | Extraction attacks |

**Bottom line:** An attacker would need to:
1. Compromise Modal's infrastructure
2. Steal the encrypted model file
3. Obtain the encryption key from Modal Secrets
4. Reverse the obfuscation
5. All while avoiding detection

This is practically impossible for a determined attacker, let alone a casual user.
