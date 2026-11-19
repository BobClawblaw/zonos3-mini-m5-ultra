# ZONOS3 Mini on one M5 Ultra

Zyphra's [ZONOS3 Mini](https://huggingface.co/Zyphra/ZONOS3-Mini) text to speech, served by TensorFold's native
Metal engine on one Mac Studio M5 Ultra (256 GB) through an OpenAI-style `/v1/audio/speech`, and speech editing on
`/v1/audio/edit`. The release is read as published (revision `2921b882`): the backbone's and the SSL teacher's
weights in bf16, the codec's in fp32, every activation, cache and sum in fp32. Nothing is converted.

It speaks in the release's 27 voices, clones a voice from a clip, takes four requests at once, and answers in WAV,
PCM, FLAC, MP3, Opus or AAC. It steers a voice with the publisher's direction vectors, keeps long readings on their
text with LACI, speaks short texts, holds a reply to a duration, and edits recorded speech.

The engine branch (`zonos3-metal`, draft ashhart/TensorFold#3732) is stacked on the ZONOS3 CUDA stack (#3720 and its
follow-ups up to #3885); it is not merged yet.

| What | Pin |
| --- | --- |
| Checkpoint | `Zyphra/ZONOS3-Mini` at `2921b8821772b0bd10a04456863d21abf9d2f283` (Apache-2.0) |
| Steering bundle, LACI heads, short-text registry | `github.com/Zyphra/ZONOS3-Mini` at `96d9e0ec1e39083ed336ac78f24e3dbc93721c0f` (MIT), fetched by `mac build` |
| Engine | BobClawblaw/TensorFold `zonos3-metal` at `ef38d3707` (tag `zonos3-metal-ef38d3707`, draft ashhart/TensorFold#3732), Zig 0.17.0 |

## Quick start

Needs an M5 Mac (M1 to M4 are untested), Python 3.11+, git, `hf`, [Zig 0.17.0](https://ziglang.org/download/) and
Rust 1.88 or later (`cargo`, for the text normalization library).

```bash
git clone https://github.com/ashhart/TensorFold ~/github/TensorFold   # mac build fetches the pin from the fork
hf download Zyphra/ZONOS3-Mini --revision 2921b8821772b0bd10a04456863d21abf9d2f283 --local-dir ~/models/ZONOS3-Mini
cp local.example.toml local.toml      # then set zig (and paths, if yours differ)
python3 -m mac build                  # the pinned engine, libzyphra_textnorm and the publisher's assets, under ~/.cache/zonos3-mini-m5
python3 -m mac up                     # http://127.0.0.1:30117/v1, model "zonos3-mini"
python3 -m mac say "The harbor was quiet this morning." --voice rupert -o reply.wav
```

`python3 -m mac down|status|logs|command|validate` stop, inspect and check it; `python3 -m mac page` serves the
engine's browser test page for the running server on `ui_port` (30118). To keep it running from login:
`python3 -m mac launchd --host 127.0.0.1 --port 30120` writes `~/Library/LaunchAgents/com.zyphra.zonos3-mini.plist`
(not loaded; `--host 0.0.0.0` serves the LAN), then `launchctl bootstrap gui/$(id -u)
~/Library/LaunchAgents/com.zyphra.zonos3-mini.plist`.

    curl -s 127.0.0.1:30117/v1/audio/speech -H 'Content-Type: application/json' \
      -d '{"model": "zonos3-mini", "input": "The harbor was quiet this morning.", "voice": "rupert", "seed": 1}' -o reply.wav

Four requests are spoken at once (`parallel`), each giving the audio it gives alone; one more that arrives meanwhile gets 503.

- **Voices:** the release's 27 are listed at `/v1/voices`. OpenAI's stock names (`alloy`, `nova`, ...) speak in the
  default voice; `speaker_reference_codes` takes a voice's codes directly.
- **Cloning:** `ref_audio` is a base64 WAV clip, half a second to 60 s (longer is cut at 60 s). The first clip loads
  the clip encoder (about 8 s, 5.26 GiB more); it then stays loaded.
- **Formats:** `response_format` is `wav` (the default), `pcm`, `flac`, `mp3`, `opus` or `aac`, at 44.1 kHz mono
  (Opus at 48 kHz). MP3, Opus and AAC need LAME, libopus and FDK AAC, which the server finds in Homebrew
  (`brew install lame opus fdk-aac`); the others need nothing. `"stream": true` takes `pcm`, and a `pcm` reply names
  its rate in `X-Audio-Sample-Rate`.
- **Sampling:** `temperature`, `top_p`, `top_k` (1 to 4096) and `seed`; condition values (speaking rate and the
  rest) and speaker guidance.
- **Steering:** `controls` names directions from the publisher's bundle (`GET /v1/audio/controls` lists its 65),
  over the whole reply or on spans of the text, which can follow the reading position.
- **LACI and short texts:** `"laci": true` watches where the reading is and regenerates what went wrong;
  `duration_seconds` holds a reply to a length; a text of a word or two is spoken whole.
- **Decoders:** `"decoder": "full_mr"` decodes through the release's full-size decoder (loaded on first use).
- **Speech editing:** `POST /v1/audio/edit` replaces a span of a clip, or the words that changed between its
  transcript and a target text, in the clip's voice; `/v1/audio/edit/align` places a transcript's words in a clip.
- **Text normalization:** written text becomes its spoken form first ("$5" is read "five dollars") through
  Zyphra's own [zyphra-textnorm](https://github.com/Zyphra/zyphra-textnorm) 0.2.0, which `mac build` builds with
  cargo beside the engine. `language` picks its grammar (`en_us` by default, `en_gb`, `fr_fr`, `de`, `pt_br`, `ja`,
  `cmn` and 37 more); `"text_normalization": false` speaks the text as typed.

## Settings

`recipe.toml` holds the defaults; `local.toml` overrides them for one Mac, and an environment variable of the same
name in upper case overrides both (`PORT=30120 python3 -m mac up`).

| setting | default | |
|---|---|---|
| `model_dir` | `~/models/ZONOS3-Mini` | the release as downloaded |
| `tensorfold_src` | `~/github/TensorFold` | a TensorFold clone; `build` adds a worktree of the pin under `tf_cache` |
| `binary` | | a built `tensorfold-native` to serve instead of building the pin |
| `host`, `port` | 127.0.0.1, 30117 | where the API listens |
| `ui_port` | 30118 | the test page (`python3 -m mac page`) |
| `context` | 4096 | a request's window, prompt rows and frames (1025 to 32768); 2,000 frames (23 s) a reply |
| `parallel` | 4 | requests at once (1 to 16) |
| `steer`, `steer_bundle` | true, | load the fetched steering bundle, or another bundle file |
| `laci` | true | load the LACI heads and the short-text registry |
| `api_key` | | a key the server requires, if set |

**Memory.** 4.40 GiB after the load at `context` 4096 and `parallel` 4 (the edit adapter included); then, on first
use, 5.26 GiB for the clip encoder, 6.63 GiB for the `full_mr` decoder and its lanes, 2.22 GiB for the aligner. Each
part loads to exactly what the server admits for it; `up` refuses to start with less than 19 GiB free.

### Hermes

On the measured Mac the server runs from the launchd unit on `127.0.0.1:30120`, and Hermes speaks through it with its
OpenAI provider:

```yaml
tts:
  provider: openai
  streaming:
    provider: openai
  openai:
    api_key: local            # any value; the server has no key
    base_url: http://127.0.0.1:30120/v1
    model: zonos3-mini
    voice: rupert             # one of /v1/voices
    pcm_sample_rate: 44100
```

Through Hermes's own TTS code: MP3 and Ogg Opus files, and its PCM streamer (6.2 s of audio in 10 chunks at 44.1
kHz).

## Measured

All on one M5 Ultra (256 GB, macOS 27.2), the binary `python3 -m mac build` makes from the pin (`ef38d3707`), served
as `python3 -m mac up` serves it.

### Served, through the recipe harness

`python3 -m harness run zonos3-mini-m5 --plan P` for the seven speech plans (2026-11-19, files in
`evidence/2026-11-19-speech/`). Every plan passes; each case once after a server start, then twice whole and twice
streamed, and every reply repeats byte for byte and streams the same bytes.

| Plan | Cases | Whole, times real time | What else it checked |
| --- | --- | --- | --- |
| `speech` | passage 17.8 s, short, second voice, clone | 0.97 s for the passage (18.3); clone 1.20 s (4.3) | streamed first byte 0.06 s (clone 0.95 s); MP3, Opus, FLAC; three at once all 200; 5 of 5 refusals |
| `speech-normalize` | written text | 15.8 | 6 of 6 written forms give their spoken forms' audio; 1 of 1 refusal |
| `speech-controls` | plain, guided, slow, fast, `full_mr` | 14.9 to 17.0; `full_mr` 8.2 | 4 of 4 settings that must change nothing; 5 of 5 refusals |
| `speech-concurrent` | six cases, five mixes | 6.9 to 29.6 in total | 18 of 18 replies at once equal to the reply alone; six at once: four 200, two 503 |
| `speech-steer` | steered, embedding, reshaped, span, guided | 16.3 to 17.9 | 4 of 4 settings that must change nothing; 6 of 6 refusals |
| `speech-laci` | LACI, short texts, pause, start, phonemes, following spans, a duration | 9.0 to 18.4 | 4 of 4 settings that must change nothing; 10 of 10 refusals |
| `speech-edit` | six edits (8 regions) | 1.38 to 6.62 s an edit | lengths as planned; 75 words aligned in 0.17 and 0.80 s; 5 of 5 edits at once equal to alone; 11 of 11 refusals |

- **The first request of a kind** loads its part: a clip's 9.3 to 9.4 s includes the clip encoder's load, the
  first `full_mr` reply's 8.6 s the decoder's.
- **Memory:** 4,727,824,128 bytes (4.40 GiB) after the load, 10,371,335,424 (9.66 GiB) once the clip encoder is in.
- **The same audio as before:** the `speech` plan's four replies are byte-identical to those of the previous pin
  (`52228c3dd`, one request at a time).
- **The same requests on the RTX 5090:** 31 of the 32 replies both machines' evidence holds have the same length as
  the [5090 recipe](https://github.com/BobClawblaw/zonos3-mini-rtx-5090)'s and 16-bit samples within 3 of it (SNR
  91.1 to 100.1 dB). The other, the `by-span` edit, has the same length and the same plan but differs from 1.5 s
  on, inside the edited span (36.6 dB): it is a seeded sampled edit of a clip the server spoke itself, and it repeats
  byte for byte on the Mac.
- **Not measured:** word error rate (the plans' transcriber is not set up on this Mac), and the quality suite.

### The parts against the reference

`zonos3-generate` (`zig build zonos3-generate -Doptimize=ReleaseFast`) against the publisher's PyTorch code run in
fp32 on the CPU over the same weights at `2921b88`; the dumps and their commands are in the engine's
`docs/recipes/zonos3-mini.md`. All 139 runs pass:

| Check | Result |
| --- | --- |
| Backbone, embedding and reference prompts (109 captures each) | every row's cosine 1.0000000; worst relative difference 2.3e-6 and 5.0e-6 |
| Greedy frames: voices, conditions, guided and steered requests, pause, start and pronunciation rows; prompt chunks of 1, 7, 64 and 256 rows | every frame identical at every chunk size |
| LACI: eleven requests and five duration targets; short texts; the eleven replay fixtures | positions, masks, rows and the record equal; pass |
| Spans that follow the reading, six requests | every reading, weight, delta and frame equal |
| Speech edit, seven cases | plans, prompts, rows and spliced codes equal |
| Codec decoder, `keep2_plain` and `full_mr` | cosine 1.0000000; audio SNR 114.0 and 111.3 dB; in chunks bit-identical to one pass |
| Speaker encoder; aligner | every stage at cosine 1.0000000; 76 of 80 words identical, the rest within 1 ms |

Served through the engine at `--parallel 4`, the 35 greedy reference requests come back at the reference's length
within 61.9 to 76.2 dB of its audio, and the eleven reference edits at exactly the SNRs the RTX 5090 gives.

All 40 of the family's Metal kernels are registered with TensorFold's kernel contract: `tf-kernel-contract --only
zonos3` on this Mac gives 41 of 41 registrations through gates 1 to 4, all 41 planted controls red, and no
launch-limit problems on M1 to M5. No part of the engine is tuned for speed.

## What this recipe does not do yet

- Word error rate on this Mac.
