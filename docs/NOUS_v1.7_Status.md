# NOUS Overleveringsdokument v1.7

**Dato:** 26. april 2026
**Forfatter:** Dan + Claude (assistance)
**Forrige version:** v1.6

## 1. Formål

Dette dokument beskriver den faktiske, kørende state af NOUS-projektet pr. 26. april 2026, så systemet kan genskabes hvis hardware dør, eller en ny iteration tager over.

v1.7 erstatter v1.6 fordi flere arkitektoniske beslutninger er ændret bevidst:
- Ollama → llama.cpp (llama-server) som primær LLM-runtime
- Native tool-calling implementeret via OpenAI-kompatibel API
- VAD (Silero) tilføjet til voice-pipeline
- Whisper-base → Whisper-medium (bedre dansk)
- Multi-model arkitektur planlagt (Base + Legacy + Legal) men ikke implementeret

## 2. Hardware-arkitektur

### Aktive enheder

| Enhed | Rolle | IP | Bruger | Specs |
|-------|-------|-----|--------|-------|
| Pi 5 16GB (Nous-Pi) | Sluse, RAG, TTS, proxy, ingest | 192.168.1.150 | nous | 16GB RAM, ARM Cortex-A76 |
| Jetson Orin Nano 8GB | LLM-inference, STT | 192.168.1.100 | nous | 8GB shared, 1024 CUDA cores, JetPack R36.5.0 |
| ReSpeaker XVF3800 4-Mic | Mikrofon-array | USB på Pi 5 | - | card 2, device 0 |
| Speaker | Lyd ud | 3.5mm/USB Pi 5 | - | - |
| Seagate 1TB HDD | Backup-disk | USB 3 på Pi 5 | - | UUID c41fcfae-b3f4-46fc-86fc-0fca5ba066b5, /mnt/backup-primary |
| Gigabit switch | Pi 5 ↔ Jetson | LAN | - | Dedikeret switch med uplink til hovedrouter |
| Hovedrouter | Internet + LAN | 192.168.1.1 | - | Eksisterende |

### Air-gap konfiguration

Jetson Orin Nano er konfigureret uden default route. `curl https://google.com` timer ud.
Jetson kan kun nå Pi 5 via LAN. Pi 5 = sluse til internet.
Verificeret: `ip route` på Jetson viser ingen default.

### Eksterne enheder (ikke en del af LAN)

| Enhed | Rolle |
|-------|-------|
| ThinkCentre Windows | Dans arbejdsstation, GPG private key, paperkey backup |
| 1TB ekstern disk | Offline GPG nøgle redundans |

### Forventet hardware-opgradering

Jetson Orin NX 16GB (anmodet via buddy). Bruges til primær LLM, hvor Nano demoteres til lyd-pipeline.

## 3. Netværk

- Hovedrouter: 192.168.1.0/24
- Pi 5: 192.168.1.150 (eth0, statisk via DHCP-reservation)
- Jetson: 192.168.1.100 (eth0, statisk)
- Pi 5 og Jetson på dedikeret gigabit switch med uplink til hovedrouter
- ThinkCentre: dynamisk DHCP

Bemærk: Pi 5 skiftede IP fra .87 til .150 søndag 26. april. Bør sættes statisk i hovedrouter.

## 4. Services kørende på Pi 5

### nous-proxy (port 8090)

- Path: `/srv/nous/proxy/nous_proxy.py`
- Service: `/etc/systemd/system/nous-proxy.service`
- Run as: nous, venv `/srv/nous/pipeline/.venv`
- Endpoints: `/health`, `/time`, `/weather`, `/search`, `/fetch`
- ALLOWED_CLIENTS: 192.168.1.100 (Jetson)
- SearXNG URL: `http://localhost:8080` (intern Docker)

### SearXNG (Docker container)

- Container: `nous-searxng`
- Image: `searxng/searxng:latest`
- Port: localhost:8080 (intern host port)
- Status: kørende

### Qdrant (vektordatabase)

- Status: dokumenteret i v1.6, ikke verificeret i denne session
- 7 collections planlagt: boernesag_secret, fbf_data_private, jura_private, dans_profil_private, familie_private, nous_projekt_swarm, swarm_public

### Backup-pipeline

- Daglig kl 03:00 cron-job
- GPG-krypteret, recipient: NOUS Backup <danbc@protonmail.com>
- GPG fingerprint: 8896CF46E6B5A10D3130D436A8035C754BC577C4
- Target: /mnt/backup-primary (Seagate 1TB)

## 5. Services kørende på Jetson

### whisper-server (port 8080)

- Path: `/opt/whisper.cpp/build/bin/whisper-server`
- Model: `/opt/whisper.cpp/models/ggml-medium.bin` (1.5GB)
- Service: `/etc/systemd/system/whisper-server.service`
- CUDA: aktiv via /usr/local/cuda
- Sprog: dansk (`--language da`)
- RAM: ~1.3GB i drift

### llama-server (port 8081)

- Path: `/opt/llama.cpp/build/bin/llama-server`
- Model: `/home/nous/models/Qwen3-4B-Instruct-2507-Q4_K_M.gguf` (2.4GB)
- Service: `/etc/systemd/system/llama-server.service`
- CUDA: 100% GPU offload, 37/37 layers
- Context: 4096 tokens
- Template: Jinja (--jinja flag)
- RAM/VRAM: ~3GB
- API: OpenAI-kompatibel (/v1/chat/completions)
- Tool-calling: native support via Qwen3 chat-template

### Ollama (legacy, stoppet)

- Service stoppet, `nous-da3` modelfile bevares som backup
- Kan startes hvis llama-server fejler

### Headless mode

- Default target: multi-user.target (uden desktop)
- Kommando for at gå tilbage til desktop: `sudo systemctl set-default graphical.target`
- Ekstra ~1.5GB RAM tilgængelig vs. desktop-mode

## 6. Voice-pipeline

### Komponenter

```
Mikrofon (ReSpeaker)
  ↓
sounddevice + Silero VAD (Pi 5)
  ↓
Whisper STT (Jetson:8080) - dansk
  ↓
llama-server (Jetson:8081) - Qwen3-4B med tools
  ↓
nous-proxy (Pi 5:8090) - tool-execution
  ↓
llama-server (Jetson:8081) - formulér dansk svar
  ↓
Tekst-rensning (markdown, emojis, links)
  ↓
Piper TTS (Pi 5, da.onnx)
  ↓
sox + ALSA (48kHz stereo)
  ↓
Højtaler
```

### Hovedscript

- Path: `/srv/nous/scripts/voice_chat.py`
- Run: `source /srv/nous/pipeline/.venv/bin/activate && python3 /srv/nous/scripts/voice_chat.py`
- VAD threshold: 0.4 (detekter)
- Pre-roll buffer: 16 frames (~512ms før detection)
- Silence hang: 25 frames (~800ms før stop)
- Max recording: 15 sek

### Performance

- VAD detection start: <100ms
- Whisper transkription: ~1-2 sek for 5 sek audio
- LLM tænkning + tool: ~3-8 sek
- TTS streaming: starter ~2 sek efter LLM-svar
- End-to-end: ~10-15 sek typisk

## 7. Tool-calling

### Native via OpenAI-API

llama-server udstiller `/v1/chat/completions` med `tools`-parameter. Qwen3-4B understøtter native tool-calling.

### Definerede tools

1. `get_time` - aktuel dato/tid i Danmark
2. `get_weather(location)` - vejr for dansk by
3. `search_web(query)` - SearXNG-søgning

### Orchestration

`voice_chat.py` håndterer multi-turn tool-loop:
1. Send user message + tools til llama-server
2. Hvis svar har `tool_calls`: kald proxy, send tool_result tilbage
3. Loop indtil ren tekst-svar (max 5 iterationer)

## 8. Privacy Guard og scopes (fra v1.6)

Status: Ikke ændret i denne session. Se v1.6 §3.3-3.6 for fuld specifikation.

Implementeret af Kimi:
- `/srv/nous/pipeline/privacy_guard.py` - PII detection + anonymisering
- `/srv/nous/scripts/promote.py` - scope-promotion
- `/srv/nous/scripts/nous-setup-collections.py` - Qdrant collections

Kendte issues (P1, ikke blockers):
- DK_PHONE regex matcher CVR/8-cifret datoformat (false positives)
- DK_ADDRESS regex misser bestemt form (vejen, gaden) og flertal

## 9. Software-stack versioner

### Pi 5

- OS: Raspberry Pi OS Debian-baseret, kernel 6.12.75
- Python: 3.13 (i venv `/srv/nous/pipeline/.venv`)
- Pakker (kritiske): fastapi, uvicorn, httpx, silero-vad 6.2.1, torch 2.11.0+cpu, sounddevice, piper

### Jetson

- OS: Ubuntu 22.04 LTS, JetPack R36.5.0, kernel 5.15.185-tegra
- CUDA: 12.6
- whisper.cpp: bygget fra source (commit ukendt, GGUF unknown)
- llama.cpp: bygget fra source 26. april (latest main)

## 10. Hvad virker (verificeret end-to-end)

- ✅ Hardware-installation, air-gap, switch
- ✅ GPG-backup setup
- ✅ Whisper STT (medium-modellen, dansk)
- ✅ llama-server med Qwen3-4B
- ✅ Tool-calling (time, weather, search) end-to-end via voice
- ✅ nous-proxy med 5 endpoints
- ✅ Voice-pipeline: mic → VAD → STT → LLM+tools → TTS → speaker
- ✅ Streaming TTS med pre-buffer (mindre pauser)
- ✅ Tekst-rensning før TTS (markdown, emojis, URLs)
- ✅ VAD pre-roll (fanger starten af sætninger)
- ✅ Headless mode på Jetson

## 11. Hvad mangler

### P0 - Næste session

1. Wake-word detection ("Hey NOUS")
2. voice_chat som persistent service med wake-word
3. Streaming under LLM-generation (token-by-token til TTS)

### P1 - Snart

4. Multi-model arkitektur (Base + Legacy + Legal modes)
5. Tidszone-support i /time endpoint
6. v1.6 → v1.7 reconciliation af scope-rules
7. Arducam IMX519 (kabel ankommer mandag 27. april)
8. Multilingual embeddings hvis engelsk-mode skal understøttes

### P2 - Hardware-afhængigt

9. NVMe-flytning af /srv/nous fra SD-kort
10. Jetson NX 16GB (anmodet via buddy)
11. Whisper-large når NX kommer
12. XTTS-v2 voice-cloning (kun realistisk på NX)

### P3 - Fremtid

13. Legacy Engine med menneskelig verifikation (foged-scenarie)
14. 3-node pilot (bror + barndomsven) over WireGuard
15. Fine-tuning af Legacy-model på SOUL.md (Unsloth + QLoRA)
16. ACE refleksions-loop (selv-forbedrende prompts)
17. Claude Code review af hele stacken

## 12. Genskabelses-procedure

### Hvis Pi 5 dør

1. Frisk Raspberry Pi OS på nyt SD-kort
2. Statisk IP 192.168.1.150
3. Restore GPG nøgle fra ThinkCentre eller paperkey
4. Mount Seagate 1TB → /mnt/backup-primary
5. Restore Qdrant fra GPG-backup
6. Geninstaller services (se §4)
7. Re-deploy `/srv/nous/` fra git eller backup

### Hvis Jetson dør

1. Genflash JetPack R36.5.0
2. Kopier whisper.cpp og llama.cpp source fra Pi 5
3. Build begge med CUDA (`cmake -DGGML_CUDA=1 .. && make -j4`)
4. Kopier modeller til Jetson:
   - ggml-medium.bin → /opt/whisper.cpp/models/
   - Qwen3-4B-Instruct-2507-Q4_K_M.gguf → /home/nous/models/
5. Geninstaller services (se §5)
6. `sudo systemctl set-default multi-user.target` for headless

### Modeller (kan re-downloades)

- ggml-medium.bin: https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin
- Qwen3-4B-Instruct-2507-Q4_K_M.gguf: https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF
- Piper da.onnx: bevares lokalt, ikke remote-hostet (gemt på backup-disk)

## 13. Kreditering

Se separat fil: `/srv/nous/docs/CREDITS.md`

Hovedkomponenter:
- Whisper (OpenAI / ggerganov whisper.cpp) - MIT
- llama.cpp (ggerganov) - MIT
- Piper TTS (Rhasspy) - MIT
- Qwen3 (Alibaba) - Apache 2.0
- Unsloth GGUF-quantization - MIT
- SearXNG - AGPL-3.0
- Qdrant - Apache 2.0
- FastAPI - MIT
- Silero VAD - MIT
- Inspiration: jetson-orin-kian (aschweig) - MIT

## 14. Designprincipper bevaret fra v1.6

- Lokalt-først: ingen cloud-AI for personlige data
- Privacy by default: scope-baseret data-håndtering
- Air-gap: Jetson uden internet, Pi 5 som sluse
- Open source: alle komponenter MIT/Apache/AGPL
- Familie-fokus: NOUS skal kunne overleve Dan (Legacy Engine)

## 15. Beslutninger truffet i denne session

1. **Ollama → llama.cpp:** Native tool-calling kræver det. Færre lag i stacken.
2. **Qwen3-4B over qwen2.5:7b:** Mindre RAM, bedre tool-calling, nyere model.
3. **Whisper-medium over -small:** Markant bedre dansk transkription.
4. **VAD med pre-roll:** Fixed 6-sek optagelse erstattet, fanger starten af sætninger.
5. **Wake-word som næste skridt:** "Always-on" UX over manuel start/stop.
6. **Multi-model arkitektur (planlagt):** Base for tænkning, Legacy for Dan-personlighed, Legal for jura. Adskilles for at undgå krydskontaminering.

