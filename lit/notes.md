# Literature notes: vision vs text robustness under adversarial UI (FLAIRS-40)

Research question: when a site uses UI tricks that are hard for bots but easy for humans (DOM order shuffled but visual order kept, hidden decoy text, text drawn as canvas or images, homoglyphs and zero-width characters, random class names, visual noise and overlays, restyled layouts), do small local vision models reading screenshots pull information out of a Mastodon timeline better than text-only LLMs reading the HTML? The models must run on one RTX 3090 (7-30B).

All 40 entries were checked against their arXiv abstract page (or the venue page) on 2026-11-15. Keys match `references.bib`.

Counts: **main = 20**, **related = 20**. By cluster: A = 12, B = 5, C = 10, D = 7, E = 6.

---

## MAIN (directly about our question)

### zheng2024seeact (SeeAct) — main — A
- Summary: Tests GPT-4V as a web agent on live sites. With a human doing the grounding it finishes about half the tasks, beating text-only LLMs. Grounding is the bottleneck, and the best automatic grounding mixes HTML with the image.
- How it relates: The closest direct comparison of visual and HTML inputs for web tasks. But it uses a large closed model, clean pages and no adversarial changes.

### he2024webvoyager (WebVoyager) — main — A
- Summary: A multimodal web agent that works from screenshots and reaches about 59% success on real websites. It beats a text-only version of the same agent.
- How it relates: Evidence that screenshots help on real sites. Our study asks whether that gap gets bigger when the HTML is made hostile on purpose.

### hong2023cogagent (CogAgent) — main — A
- Summary: An 18B VLM built for GUIs with a high-resolution image branch. Using only screenshots, it beats LLM methods that read extracted HTML on Mind2Web and AITW.
- How it relates: A model about the size we can run, showing screenshot-only input can beat HTML input. We extend this from navigation to extraction under attack.

### koh2024visualwebarena (VisualWebArena) — main — A
- Summary: A benchmark of web tasks that need visual understanding. It points out clear limits of text-only LLM agents and gaps that remain in multimodal ones.
- How it relates: Gives the standard text-only vs multimodal agent framing. Its tasks are visual by design; ours make text input hard on purpose.

### liu2024visualwebbench (VisualWebBench) — main — A
- Summary: A benchmark of webpage understanding and grounding tasks (captioning, OCR, QA, element grounding) for multimodal LLMs. Open models are weak at grounding on text-heavy pages and at low resolution.
- How it relates: The closest benchmark to screenshot-based webpage reading. It warns us that small VLMs may struggle with dense timelines and small engagement numbers.

### wang2026pixelrag (PixelRAG) — main — A/B
- Summary: Retrieves web pages as screenshots and gives them straight to a VLM instead of parsing them to text. It beats text-based RAG even on text-heavy QA. It is built on Qwen3-VL embeddings.
- How it relates: Very recent (June 2026) evidence that pixels can beat parsed text for web content even without attacks. That supports our hypothesis that vision loses less information.

### kim2025nexteval (NEXT-EVAL) — main — B
- Summary: A benchmark for LLM web data record extraction. It shows that the input format (flat JSON, slimmed HTML, hierarchical JSON) swings F1 and hallucination rate a lot.
- How it relates: Shows that text-based extraction is fragile to how the DOM is fed in, which is exactly what DOM shuffling and decoys attack. A good source for text-pipeline baselines.

### zhang2024popups (Pop-up attacks) — main — C
- Summary: Adversarial pop-ups added to OSWorld and VisualWebArena pull VLM agents off task with about 86% attack success. Simple prompt defenses barely help.
- How it relates: The vision-side weakness that matches our "overlay or visual noise" change. It is a key counterpoint: screenshots are not automatically robust.

### liao2024eia (EIA) — main — C
- Summary: Adds hidden or blended injected elements to web pages to make agents leak private user data. The attack works often and is hard to detect.
- How it relates: Shows that HTML-level hidden content (like our decoy text) can steer agents. It is a model for building our "invisible to humans, visible to the parser" changes.

### ma2024caution (Environmental distractions) — main — C
- Summary: Even strong multimodal GUI agents get distracted by unrelated on-screen content when nobody means harm.
- How it relates: Our visual noise and decoy changes act like non-malicious distractions. This suggests VLMs may also lose accuracy, not just text models.

### wu2025dissecting (Dissecting adversarial robustness) — main — C
- Summary: Builds VisualWebArena-Adv and attacks single parts of agent pipelines (image, caption, text). Image and text attacks both hijack agents, and adding a captioner can carry image attacks into text.
- How it relates: The most careful study of how attack modality matters. Its finding that a captioner can carry an attack across modalities is important for any hybrid pipeline we test.

### cheng2024typographic (Typographic deceptions) — main — C
- Summary: Misleading text placed inside images greatly hurts large VLMs. The authors propose ways to reduce the drop.
- How it relates: A vision-specific failure (text drawn in the image misleads the model). That applies directly to decoy text drawn into canvas or images.

### ersoy2026darkpatterns (Dark patterns on web agents) — main — C
- Summary: Measures how often LLM web agents fall for dark patterns (about 41% for a single pattern). Changing the pattern's visual design or its HTML changes how vulnerable the agent is. Accepted to IEEE S&P 2026 per the arXiv HTML header.
- How it relates: Directly changes both visual and HTML presentation and measures the effect, which is close to our split between the two inputs. Its tasks are actions, not extraction.

### cuvin2025decepticon (DECEPTICON) — main — C
- Summary: A benchmark showing dark patterns push web agents into bad outcomes in over 70% of tasks, versus about 31% for humans. Larger models were more vulnerable.
- How it relates: A clear human-vs-agent gap on UI manipulation, plus the surprising scaling result. That matters when we compare 7B and 30B models.

### cao2026vpibench (VPI-Bench) — main — C
- Summary: A benchmark of prompt injections embedded in what the agent sees, for computer-use and browser-use agents. Attacks often work and system-prompt defenses help little. ICLR 2026.
- How it relates: Shows that vision input brings its own injection surface. This is the other side of our hypothesis and should be discussed as a threat to validity.

### verma2025htmlinjection (HTML injection in summarization) — main — C
- Summary: Hidden HTML (meta tags, aria-labels, alt text) changes LLM summaries while the rendered page looks the same. Tested on Llama 4 Scout and Gemma 9B.
- How it relates: Almost exactly our "hidden decoy text" condition against small open text models. Screenshot readers would not see these elements at all.

### boucher2022badcharacters (Bad Characters) — main — D
- Summary: Invisible characters, homoglyphs, reordering controls and deletion characters break text NLP models, including commercial ones, without changing how the text looks. IEEE S&P 2022.
- How it relates: The foundational paper for our homoglyph and zero-width conditions. These attacks target the text layer and should have no effect on pixels.

### rust2022pixel (PIXEL) — main — D/E
- Summary: A language model that reads text rendered as images instead of tokens. It is more robust than BERT to orthographic attacks and code-switching.
- How it relates: Direct evidence that reading pixels resists character-level obfuscation. This is the mechanism we expect VLMs to benefit from.

### salesky2021robust (Visual text representations for MT) — main — D
- Summary: Translation models that read rendered text images stay robust to character noise and permutations that wreck subword models. EMNLP 2021.
- How it relates: Older but clean evidence that visual text input is robust to the same kinds of noise our obfuscations add.

### thomas2025webgames (WebGames) — main — D
- Summary: Over 50 web challenges that are easy for humans and hard for agents. Humans score about 96%, the best AI about 43%.
- How it relates: Turns the human-vs-bot gap on web pages into numbers, which is the asymmetry our adversarial changes rely on.

---

## RELATED (background / future work)

### lee2023pix2struct (Pix2Struct) — related — A/E
- Summary: Pretrains an image-to-text model to turn masked web screenshots into simplified HTML, then fine-tunes it for visual language tasks. ICML 2023.
- How it relates: The origin of "screenshot to structure" learning, a conceptual ancestor of screenshot-based extraction.

### cheng2024seeclick (SeeClick / ScreenSpot) — related — A
- Summary: A screenshot-only GUI agent pretrained on grounding, plus the ScreenSpot grounding benchmark.
- How it relates: Background on visual grounding. Our extraction task needs reading more than clicking.

### qin2025uitars (UI-TARS) — related — A
- Summary: An end-to-end native GUI agent that sees only screenshots, with state-of-the-art results on many GUI benchmarks. It comes in sizes that fit local GPUs.
- How it relates: A candidate local vision model, and evidence that pure-pixel agents are now competitive.

### lu2024omniparser (OmniParser) — related — A
- Summary: Parses UI screenshots into labeled interactive elements and descriptions using vision only, to help VLM agents ground actions.
- How it relates: An option for a "vision-to-structure" pipeline that skips the DOM entirely. It could be a third condition in future work.

### deng2023mind2web (Mind2Web) — related — A/B
- Summary: A large dataset of web tasks across real sites. It uses a small model to filter raw HTML before an LLM acts.
- How it relates: The standard HTML-based agent pipeline. Shows that text agents rely on HTML cleaning that adversarial DOMs would break.

### zhou2023webarena (WebArena) — related — A
- Summary: A self-hosted, realistic web environment. The best GPT-4 agent finished about 14% of tasks, versus about 78% for humans.
- How it relates: Background and a possible testbed. Self-hosting (like a local Mastodon instance) is the method we copy.

### li2022markuplm (MarkupLM) — related — B
- Summary: Pretrains jointly on text and markup (XPath) to understand web pages better. ACL 2022.
- How it relates: The classic structure-aware text model. Randomized class names and shuffled DOM order attack exactly the structure it depends on.

### gur2023html (Understanding HTML with LLMs) — related — B
- Summary: Shows general pretrained LLMs fine-tune well for HTML classification, description and navigation. Findings of EMNLP 2023.
- How it relates: The baseline claim that LLMs "understand HTML". We test whether that holds under hostile markup.

### huang2024autoscraper (AutoScraper) — related — B
- Summary: Uses LLMs to write reusable web scrapers by exploring the HTML hierarchy and similarities across pages. EMNLP 2024.
- How it relates: The kind of LLM scraper that anti-bot UI tricks are meant to defeat. A good representative for the text side.

### tan2024htmlrag (HtmlRAG) — related — B
- Summary: Argues that keeping cleaned and pruned HTML beats plain text for RAG over web pages. ACM DOI (likely WWW 2025; venue name not shown on the arXiv page).
- How it relates: The opposite view to PixelRAG: structure helps text models. Useful for framing "HTML vs text vs pixels".

### greshake2023indirect (Indirect prompt injection) — related — C
- Summary: Introduces indirect prompt injection, where hidden instructions in fetched content take over LLM-integrated apps such as Bing Chat.
- How it relates: The root threat model for hidden web content. Our decoys are a non-instruction cousin of it.

### luo2025opencaptchaworld (Open CaptchaWorld) — related — D
- Summary: A web platform of interactive CAPTCHA puzzles for multimodal agents. Humans reach about 93%, the best agent about 40%.
- How it relates: Human-easy, bot-hard puzzles aimed at vision agents. This frames where vision robustness might stop.

### ding2025illusioncaptcha (IllusionCAPTCHA) — related — D
- Summary: A CAPTCHA based on visual illusions that most humans pass while GPT-4o and Gemini fail completely. WWW 2025.
- How it relates: Shows site owners can design visual changes that also beat VLMs. A future-work threat for screenshot scrapers.

### venugopalan2024fpinconsistent (FP-Inconsistent) — related — D
- Summary: Measures how commercial bot services evade DataDome and BotD, and detects them through inconsistent browser fingerprints.
- How it relates: Background on network and browser-level bot detection, which is separate from the content-level obfuscation we study.

### bai2025qwen25vl (Qwen2.5-VL) — related — E
- Summary: An open VLM family (3B, 7B, 72B) with strong document parsing, grounding and agent abilities.
- How it relates: The main candidate local vision model (7B fits on a 3090).

### bai2025qwen3vl (Qwen3-VL) — related — E
- Summary: The next Qwen VLM family, with dense 2B/4B/8B/32B models and 30B-A3B/235B-A22B MoE models, and a 256K context.
- How it relates: The 8B and 30B-A3B variants are in our size budget. It is also the base model of PixelRAG.

### gemmateam2025gemma3 (Gemma 3) — related — E
- Summary: Google's open models from 1B to 27B, which add image understanding.
- How it relates: A second candidate vision model family. It also lets us compare the same model with and without vision input.

### nvidia2025nemotronvl (Nemotron Nano V2 VL) — related — E
- Summary: NVIDIA's VLM built on a hybrid Mamba-Transformer, aimed at document understanding and long video. It ships with BF16, FP8 and FP4 checkpoints. NVIDIA's model page names it a 12B model.
- How it relates: A third candidate vision model. Low-precision checkpoints help it fit on a 3090.

### kim2022donut (Donut) — related — E
- Summary: An OCR-free transformer that reads document images straight to structured output. ECCV 2022.
- How it relates: The main reference for OCR-free extraction, the idea behind skipping both OCR and the DOM.

### liu2023ocrbench (OCRBench) — related — E
- Summary: A benchmark showing large multimodal models do unevenly on text in images, with clear weaknesses on handwritten, multilingual and non-semantic text.
- How it relates: Predicts where VLMs may fail on our "text as image" and noise conditions (for example random handles or numbers).

---

## Gap our paper fills

- No prior work compares screenshot input with HTML/text input on **information extraction** (as opposed to navigation or actions) under **controlled, human-invisible adversarial UI changes**. Existing robustness work attacks agents' actions (pop-ups, dark patterns, injections), not field-level extraction accuracy.
- Prior robustness studies mostly use large closed models (GPT-4V/4o, Claude, Gemini). There is little evidence for **small open models (7-30B) that run locally on one consumer GPU**.
- Obfuscation work on homoglyphs and zero-width characters (Bad Characters, PIXEL) is done on classic NLP tasks. Nobody has applied it to **real web DOMs** alongside layout changes such as DOM shuffling, canvas text and randomized class names.
- **Social media timelines** (several posts, each with author, text, links, text inside images and engagement counts) are not a target in any web agent or web IE benchmark we found. Most benchmarks use shopping, forums, CMS or general sites.
- We break results down **per attack type**, giving a matrix of which changes hurt text models, which hurt vision models, and which hurt both (for example overlays and typographic decoys likely hurt vision, while hidden DOM text likely hurts text).

## Closest prior work (top 5)

1. **wu2025dissecting**: The most systematic study of how attack modality (image vs text vs captioner) affects multimodal web agents. It is the nearest methodological model for our modality comparison, but it targets agent actions, not extraction.
2. **ersoy2026darkpatterns**: Changes the visual design and the HTML of manipulative UI separately and measures the agent's response. This is the closest to our "same content, changed presentation" setup.
3. **zheng2024seeact**: Directly compares HTML-only, image-only and combined inputs for web agents and finds visual input helps. It is our main baseline claim, though without adversarial pages.
4. **verma2025htmlinjection**: Hidden HTML elements that are invisible when rendered change small open text LLMs' outputs (Gemma 9B, Llama 4 Scout). This is almost exactly our hidden-decoy condition, but text-only, with no vision comparison.
5. **wang2026pixelrag**: Shows screenshots beat parsed text for reading web content with a Qwen3-VL-based system, on clean pages. We test whether this advantage grows under adversarial changes.

(Runner-up: **rust2022pixel** and **boucher2022badcharacters** together give the mechanism for why pixels should resist character-level obfuscation.)
