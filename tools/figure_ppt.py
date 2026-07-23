#!/usr/bin/env python3
"""figure_ppt.py — model-figure pipeline: paper → BioRender prompt → gpt-image → editable PPT → PDF.

The mechanism (per the researcher):
  1. GENPROMPT  the fixed "expert scientific-figure designer" META_PROMPT (system) + the paper
                (user), nothing appended, via GPT chat → a BioRender-style image prompt written
                into spec.draw_prompt. The draw prompt is GENERATED from the paper, not hand-written.
  2. DRAW       that prompt drives an image model VERBATIM (nothing appended). Drawer swappable:
                --provider openai (gpt-image-1, OPENAI_API_KEY) now; gemini later. Every draw is
                ARCHIVED to iterations/<id>/round_NN.png + round_NN.prompt.txt (no overwrite).
  3. REFINE     AGENT-DRIVEN, no CLI command: the calling agent READS the drawn image, decides
                what is wrong, rewrites spec.draw_prompt itself, re-runs draw. Loop. (First-draft
                failures can't be enumerated in a fixed instruction, so there is no scripted refine.)
  4. BUILD+PDF  two paths — `buildshapes` renders a shape-spec into NATIVE editable PPT shapes
                (every element editable, crisp text); `build` lays the image as a background +
                editable label text boxes. `pdf` = soffice (LibreOffice, headless) pptx→pdf.

Subcommands:
  genprompt --paper <file> --spec spec.json [--model gpt-4o]   -> writes spec.draw_prompt
  draw        spec.json  [--provider openai]                   -> <fig>.bg.png (+ iterations/)
  build       spec.json  [--img <png>]                         -> <fig>.pptx  (image bg + labels)
  buildshapes shapes.json [--out <fig>.pptx]                   -> <fig>.pptx  (fully editable shapes)
  pdf         <fig>.pptx                                        -> <fig>.pdf
  all         spec.json  --paper <file>                        -> genprompt→draw→build→pdf
  emit-example                                                 -> starter spec
  (refine is agent-driven: read <fig>.bg.png, edit spec.draw_prompt, re-run draw.)
"""
import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request

# ---------- the fixed prompt-generation meta-prompt (verbatim, per the researcher) ----------
META_PROMPT = (
    "You are a professional and experienced scientific-figure designer. Carefully read the "
    "following paper content, deeply understand its core mechanism, key method, and deep-model "
    "experimental pipeline, and then generate a BioRender-style prompt for the mechanism figure."
)
def _openai_chat_raw(model, messages):
    key = os.environ.get("OPENAI_API_KEY") or sys.exit("OPENAI_API_KEY not set")
    body = json.dumps({"model": model, "messages": messages}).encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions", data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)["choices"][0]["message"]["content"].strip()


def _openai_chat(model, system, user):
    return _openai_chat_raw(model, [{"role": "system", "content": system},
                                    {"role": "user", "content": user}])


# NOTE: there is deliberately NO scripted "refine" step. First-draft figures fail in ways that
# cannot be enumerated in a fixed instruction, so REFINEMENT IS AGENT-DRIVEN: the calling agent
# READS the drawn image, decides what is actually wrong, rewrites `spec.draw_prompt` itself
# (Write/Edit the spec), and re-runs `draw`. See SKILL.md Stage 3.


def cmd_genprompt(args):
    paper = open(args.paper, encoding="utf-8", errors="replace").read()
    # only the meta-prompt (system) + the paper (user); nothing appended.
    prompt = _openai_chat(args.model, META_PROMPT, paper)
    if args.spec and os.path.exists(args.spec):
        spec = json.load(open(args.spec))
        spec["draw_prompt"] = prompt
        json.dump(spec, open(args.spec, "w"), ensure_ascii=False, indent=2)
        print(json.dumps({"genprompt": "written to spec.draw_prompt", "spec": args.spec,
                          "chars": len(prompt)}, ensure_ascii=False))
    print(prompt)


# ---------- 2. DRAW (swappable image model) ----------
def draw_openai(prompt, size, out_png, quality="high"):
    key = os.environ.get("OPENAI_API_KEY") or sys.exit("OPENAI_API_KEY not set")
    body = json.dumps({"model": "gpt-image-1", "prompt": prompt, "size": size,
                       "quality": quality, "n": 1}).encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/images/generations", data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        data = json.load(r)
    with open(out_png, "wb") as f:
        f.write(base64.b64decode(data["data"][0]["b64_json"]))
    return out_png


def draw_gemini(prompt, size, out_png, quality="high"):
    sys.exit("gemini provider not wired yet (needs GEMINI_API_KEY + google-generativeai); "
             "use --provider openai for now")


DRAWERS = {"openai": draw_openai, "gemini": draw_gemini}


def _archive_iteration(spec_path, fid, img, prompt):
    """Save every iteration (image + the exact prompt used) so nothing is overwritten."""
    d = os.path.join(os.path.dirname(os.path.abspath(spec_path)) or ".", "iterations", fid)
    os.makedirs(d, exist_ok=True)
    nums = [int(m.group(1)) for f in os.listdir(d) if (m := re.match(r"round_(\d+)\.png$", f))]
    n = max(nums, default=0) + 1
    shutil.copy(img, os.path.join(d, f"round_{n:02d}.png"))
    with open(os.path.join(d, f"round_{n:02d}.prompt.txt"), "w", encoding="utf-8") as f:
        f.write(prompt)
    return n, f"iterations/{fid}/round_{n:02d}"


def cmd_draw(args):
    spec = json.load(open(args.spec))
    if not spec.get("draw_prompt"):
        sys.exit("spec.draw_prompt is empty — run `genprompt --paper <file> --spec <spec>` first")
    out = args.out or f"{spec['figure_id']}.bg.png"
    # draw with the generated prompt VERBATIM — nothing appended.
    DRAWERS[args.provider](spec["draw_prompt"], spec.get("image_size", "1536x1024"),
                           out, spec.get("quality", "high"))
    n, saved = _archive_iteration(args.spec, spec["figure_id"], out, spec["draw_prompt"])
    print(json.dumps({"drew": out, "provider": args.provider, "iteration": n,
                      "saved": saved + ".png (+ .prompt.txt)"}))


# ---------- 3. BUILD editable PPTX ----------
def cmd_build(args):
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN
    spec = json.load(open(args.spec))
    W, H = spec["canvas_in"]
    img = args.img or f"{spec['figure_id']}.bg.png"
    out = args.out or f"{spec['figure_id']}.pptx"
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(W), Inches(H)
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    if os.path.exists(img):
        slide.shapes.add_picture(img, 0, 0, width=Inches(W), height=Inches(H))
    align = {"left": PP_ALIGN.LEFT, "center": PP_ALIGN.CENTER, "right": PP_ALIGN.RIGHT}
    for lb in spec.get("labels", []):
        tb = slide.shapes.add_textbox(Inches(lb["x"] * W), Inches(lb["y"] * H),
                                      Inches(lb.get("w", 0.2) * W), Inches(0.3))
        tb.text_frame.word_wrap = True
        p = tb.text_frame.paragraphs[0]
        p.alignment = align.get(lb.get("align", "center"), PP_ALIGN.CENTER)
        run = p.add_run(); run.text = lb["text"]
        run.font.size = Pt(lb.get("size", 11)); run.font.bold = lb.get("bold", False)
        run.font.name = lb.get("font", "Times New Roman")
        if lb.get("color"):
            run.font.color.rgb = RGBColor.from_string(lb["color"])
    prs.save(out)
    print(json.dumps({"built": out, "labels": len(spec.get("labels", [])),
                      "note": "open in PowerPoint to edit label text/position by hand"}))


# ---------- 3b. BUILD as fully-editable NATIVE PPT SHAPES (all elements editable) ----------
def _hx(c):
    return c.lstrip("#")


def cmd_buildshapes(args):
    """Render a shape-spec into NATIVE PPT shapes — rounded rects / ovals / arrows / text —
    so EVERY element is editable in PowerPoint (no flat background image).
    FLAT DESIGN: solid fills only, no drop shadows on any element (shapes AND connectors set
    shadow.inherit=False), no gradients, no 3D — a clean flat schematic."""
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN
    from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
    from pptx.oxml.ns import qn
    spec = json.load(open(args.spec))
    W, H = spec["canvas_in"]
    out = args.out or f"{spec['figure_id']}.pptx"
    prs = Presentation(); prs.slide_width, prs.slide_height = Inches(W), Inches(H)
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    SH = {"rounded_rect": MSO_SHAPE.ROUNDED_RECTANGLE, "rect": MSO_SHAPE.RECTANGLE,
          "oval": MSO_SHAPE.OVAL, "hexagon": MSO_SHAPE.HEXAGON, "right_arrow": MSO_SHAPE.RIGHT_ARROW}
    AL = {"left": PP_ALIGN.LEFT, "center": PP_ALIGN.CENTER, "right": PP_ALIGN.RIGHT}
    IX = lambda f: Inches(f * W)
    IY = lambda f: Inches(f * H)

    def _text(tf_owner, sh):
        tf = tf_owner.text_frame; tf.word_wrap = True
        p = tf.paragraphs[0]; p.alignment = AL.get(sh.get("align", "center"), PP_ALIGN.CENTER)
        r = p.add_run(); r.text = sh.get("text", "")
        r.font.size = Pt(sh.get("font_size", 11)); r.font.bold = sh.get("bold", False)
        r.font.name = sh.get("font", "Arial")
        if sh.get("font_color"):
            r.font.color.rgb = RGBColor.from_string(_hx(sh["font_color"]))

    def _flat(shape):
        # Flat design: NO drop shadow. shadow.inherit=False only adds an empty <a:effectLst/>, but the
        # shape's <p:style> still carries <a:effectRef idx="2"> pointing at the THEME's outer shadow,
        # and LibreOffice/soffice renders THAT on the pptx->pdf export (PowerPoint honours the override,
        # soffice does not). Neutralize the reference (idx="0") so no renderer draws a shadow.
        shape.shadow.inherit = False
        for eff in shape._element.iter(qn("a:effectRef")):
            eff.set("idx", "0")

    for sh in spec.get("shapes", []):
        k = sh["kind"]
        if k in SH:
            s = slide.shapes.add_shape(SH[k], IX(sh["x"]), IY(sh["y"]), IX(sh["w"]), IY(sh["h"]))
            if sh.get("fill"):
                s.fill.solid(); s.fill.fore_color.rgb = RGBColor.from_string(_hx(sh["fill"]))
            else:
                s.fill.background()
            if sh.get("line"):
                s.line.color.rgb = RGBColor.from_string(_hx(sh["line"])); s.line.width = Pt(sh.get("line_w", 1))
            else:
                s.line.fill.background()
            _flat(s)
            if sh.get("text"):
                _text(s, sh)
        elif k == "textbox":
            tb = slide.shapes.add_textbox(IX(sh["x"]), IY(sh["y"]), IX(sh.get("w", 0.2)), IY(sh.get("h", 0.08)))
            _text(tb, sh); _flat(tb)
        elif k in ("arrow", "line"):
            c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, IX(sh["x1"]), IY(sh["y1"]),
                                           IX(sh["x2"]), IY(sh["y2"]))
            c.line.color.rgb = RGBColor.from_string(_hx(sh.get("color", "5B6B73")))
            c.line.width = Pt(sh.get("weight", 2))
            _flat(c)  # flat — connectors must not inherit or reference the theme drop-shadow either
            if k == "arrow":
                ln = c.line._get_or_add_ln()
                ln.append(ln.makeelement(qn("a:tailEnd"), {"type": "triangle", "w": "med", "len": "med"}))
    prs.save(out)
    print(json.dumps({"built_shapes": out, "n_shapes": len(spec.get("shapes", [])),
                      "note": "fully editable native PPT shapes — every element selectable/editable"}))


# ---------- 4. PPTX -> PDF ----------
def cmd_pdf(args):
    outdir = os.path.dirname(os.path.abspath(args.pptx)) or "."
    soffice = next((p for p in ("/opt/homebrew/bin/soffice",
                                "/Applications/LibreOffice.app/Contents/MacOS/soffice", "soffice")
                    if p == "soffice" or os.path.exists(p)), "soffice")
    subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", outdir, args.pptx],
                   check=True, capture_output=True)
    pdf = os.path.join(outdir, os.path.splitext(os.path.basename(args.pptx))[0] + ".pdf")
    print(json.dumps({"pdf": pdf, "ok": os.path.exists(pdf)}))


def cmd_all(args):
    # genprompt → draw → build → pdf. The REFINE step (read image → rewrite spec.draw_prompt →
    # redraw) is agent-driven and lives BETWEEN draw and build — do it by hand, not here.
    args.out = None
    cmd_genprompt(args)
    cmd_draw(args)
    cmd_build(args)
    spec = json.load(open(args.spec))
    args.pptx = f"{spec['figure_id']}.pptx"
    cmd_pdf(args)


EXAMPLE = {
    "figure_id": "rts_fig1",
    "canvas_in": [6.5, 3.0],
    "image_size": "1536x1024",
    "quality": "high",
    "draw_prompt": "",
    "_draw_prompt_note": "leave empty — filled by `genprompt --paper <method> --spec this.json`",
    "labels": [
        {"text": "example label", "x": 0.05, "y": 0.05, "w": 0.2, "size": 10, "align": "left"}
    ]
}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    gp = sub.add_parser("genprompt"); gp.add_argument("--paper", required=True)
    gp.add_argument("--spec"); gp.add_argument("--model", default="gpt-4o")
    for name in ("draw", "build", "buildshapes", "all"):
        p = sub.add_parser(name); p.add_argument("spec"); p.add_argument("--out")
        if name in ("draw", "all"):
            p.add_argument("--provider", choices=list(DRAWERS), default="openai")
        if name == "build":
            p.add_argument("--img")
        if name == "all":
            p.add_argument("--paper", required=True); p.add_argument("--model", default="gpt-4o")
    pp = sub.add_parser("pdf"); pp.add_argument("pptx")
    sub.add_parser("emit-example")
    args = ap.parse_args()
    if args.cmd == "emit-example":
        print(json.dumps(EXAMPLE, ensure_ascii=False, indent=2)); return
    {"genprompt": cmd_genprompt, "draw": cmd_draw, "build": cmd_build,
     "buildshapes": cmd_buildshapes, "pdf": cmd_pdf, "all": cmd_all}[args.cmd](args)


if __name__ == "__main__":
    main()
