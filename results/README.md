# Results — STYLE JAILBREAK (stylization-as-a-jailbreak)

Experiment record backing `outputs/05_FINDINGS.html`. Every number in the findings and in the
paper draft traces to one of these files.

| File | Claim | What it holds |
|---|---|---|
| `representation_analysis.json` | C1 | Vicuna-13B mid-layer probe (0.98→0.63) + enclosure (0.94→0.55), radius ~2.1×, class-mean gap ~3× |
| `headtohead_advbench.json` | C2/C3 | Full Table-1 AdvBench: 8 methods × 5 targets × {ASR, StrongREJECT}, n=470 |
| `headtohead_trustllm.json` | C2/C3 | Full Table-1 TrustLLM: 8 methods × 5 targets × {ASR, StrongREJECT}, n=200 |
| `ablation_components.json` | C4 | Component ablation (Direct 0.0 / Direct+Multi 0.7 / Style 31.7 / full 78.0 mean ASR) |
| `cost_efficiency.json` | C5 | Target queries/goal + wall-clock (AdvBench ~3h vs PAIR/ReNeLLM/TAP; TrustLLM ~90min vs TAP ~50h) |
| `mitigation_guard.json` | C6 | Input-side style-normalization guard reduces mean ASR 91.3 → ~3.0 (≈ Direct 2.9) |

Targets: DeepSeek-V3, GPT-4o, Llama-3.3-70B, Nemotron-70B, Qwen2.5-72B. ASR judge: GPT-4o
(success = score ≥ 5/10 within the query budget). StrongREJECT scored with DeepSeek-V4-Flash.
Representation study on Vicuna-13B. Benchmarks: AdvBench (n=470 test), TrustLLM (n=200).
