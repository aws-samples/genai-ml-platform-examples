#!/usr/bin/env python3
"""Regenerate images/architecture-icons.svg — the icon view of the workshop
architecture, with one band per AI lifecycle stage.

The official AWS Architecture Icons are embedded as <symbol> definitions so the
output is a single self-contained SVG that renders anywhere (GitHub, Studio,
slides) with no external asset references. Icon artwork is copied verbatim:
only element ids are namespaced, to stop ids such as "Rectangle" colliding
between symbols, and icons are placed at uniform scale. Nothing is recoloured,
cropped, rotated or distorted, and no AWS icon is used to stand for a non-AWS
product -- all of which the AWS Architecture Icons terms require.

Usage
-----
The icon package is not vendored in this repo. Fetch and unpack it first, then
run this script:

    # grab the current package URL from the official page
    curl -s -A "Mozilla/5.0" https://aws.amazon.com/architecture/icons/ \
      | grep -oE 'https://[^"]*Icon-package[^"]*\\.zip' | head -1

    curl -o /tmp/aws-icons.zip "<url from above>"
    unzip -q /tmp/aws-icons.zip -d /tmp/awsicons

    python3 scripts/generate-architecture-icons.py images/architecture-icons.svg

If the release date in the package changes, update PKG_RELEASE below -- the
directory names inside the zip are date-stamped.

Icons remain the property of Amazon.com, Inc. or its affiliates.
"""
import os
import re
import sys

PKG = os.environ.get("AWS_ICON_PKG", "/tmp/awsicons")
PKG_RELEASE = "07312026"
A = os.path.join(PKG, f"Architecture-Service-Icons_{PKG_RELEASE}")
R = os.path.join(PKG, f"Resource-Icons_{PKG_RELEASE}")

if not os.path.isdir(A):
    sys.exit(f"icon package not found at {A}\n"
             f"download and unpack it first -- see the module docstring")

# key -> (path, viewBox size, needs backing tile, human name)
ICONS = {
    "sagemaker":  (f"{A}/Arch_Artificial-Intelligence/64/Arch_Amazon-SageMaker-AI_64.svg", 80, False, "Amazon SageMaker AI"),
    "s3":         (f"{A}/Arch_Storage/64/Arch_Amazon-Simple-Storage-Service_64.svg", 80, False, "Amazon S3"),
    "athena":     (f"{A}/Arch_Analytics/64/Arch_Amazon-Athena_64.svg", 80, False, "Amazon Athena"),
    "glue":       (f"{A}/Arch_Analytics/64/Arch_AWS-Glue_64.svg", 80, False, "AWS Glue"),
    "emr":        (f"{A}/Arch_Analytics/64/Arch_Amazon-EMR_64.svg", 80, False, "Amazon EMR"),
    "cloudwatch": (f"{A}/Arch_Management-Tools/64/Arch_Amazon-CloudWatch_64.svg", 80, False, "Amazon CloudWatch"),
    "cloudtrail": (f"{A}/Arch_Management-Tools/64/Arch_AWS-CloudTrail_64.svg", 80, False, "AWS CloudTrail"),
    "quick":      (f"{A}/Arch_Business-Applications/64/Arch_Amazon-Quick_64.svg", 80, False, "Amazon Quick Suite (QuickSight)"),
    "sqs":        (f"{A}/Arch_Application-Integration/64/Arch_Amazon-Simple-Queue-Service_64.svg", 80, False, "Amazon SQS"),
    "lambda":     (f"{A}/Arch_Compute/64/Arch_AWS-Lambda_64.svg", 80, False, "AWS Lambda"),
    "vpc":        (f"{A}/Arch_Networking-Content-Delivery/64/Arch_Amazon-Virtual-Private-Cloud_64.svg", 80, False, "Amazon VPC"),
    "iam":        (f"{A}/Arch_Security-Identity/64/Arch_AWS-Identity-and-Access-Management_64.svg", 80, False, "AWS IAM"),
    "catalog":    (f"{A}/Arch_Management-Tools/64/Arch_AWS-Service-Catalog_64.svg", 80, False, "AWS Service Catalog"),
    "cfn":        (f"{A}/Arch_Management-Tools/64/Arch_AWS-CloudFormation_64.svg", 80, False, "AWS CloudFormation"),
    "notebook":   (f"{R}/Res_Artificial-Intelligence/Res_Amazon-SageMaker-AI_Notebook_48.svg", 48, True, "SageMaker AI Notebook"),
    "train":      (f"{R}/Res_Artificial-Intelligence/Res_Amazon-SageMaker-AI_Train_48.svg", 48, True, "SageMaker AI Train"),
    "model":      (f"{R}/Res_Artificial-Intelligence/Res_Amazon-SageMaker-AI_Model_48.svg", 48, True, "SageMaker AI Model"),
    "canvas":     (f"{R}/Res_Artificial-Intelligence/Res_Amazon-SageMaker-AI_Canvas_48.svg", 48, True, "SageMaker AI Canvas"),
    "bucketobj":  (f"{R}/Res_Storage/Res_Amazon-Simple-Storage-Service_Bucket-With-Objects_48.svg", 48, True, "S3 Bucket with objects"),
}

missing = [k for k, v in ICONS.items() if not os.path.isfile(v[0])]
if missing:
    sys.exit(f"missing icons: {missing}")

SVG_OPEN = re.compile(r"<svg\b[^>]*>", re.S)


def build_symbol(key, path, vb):
    raw = open(path, encoding="utf-8").read()
    raw = re.sub(r"<\?xml[^>]*\?>", "", raw)
    m = SVG_OPEN.search(raw)
    inner = raw[m.end():raw.rindex("</svg>")]
    inner = re.sub(r"<title>.*?</title>", "", inner, flags=re.S)

    # Namespace every internal id, then repoint url(#...) references at the
    # renamed ids. Guards against collisions such as id="Rectangle", which
    # several icons share, and the clipPath that the Quick icon relies on.
    ids = re.findall(r'\sid="([^"]*)"', inner)
    for i, old in enumerate(dict.fromkeys(ids)):
        new = f"{key}-i{i}"
        inner = inner.replace(f'id="{old}"', f'id="{new}"')
        inner = inner.replace(f"url(#{old})", f"url(#{new})")

    name = ICONS[key][3]
    return (f'<symbol id="ic-{key}" viewBox="0 0 {vb} {vb}">'
            f"<title>{name}</title>{inner.strip()}</symbol>")


SYMBOLS = "\n    ".join(build_symbol(k, v[0], v[1]) for k, v in ICONS.items())

# ---------------------------------------------------------------- layout data
STAGES = [
    dict(n="1", name="INFRA SETUP", sub="platform foundation", lab="Lab 1",
         persona="Platform Admin", colour="#4B5563", tint="#EEF2F6", ptint="#f2f4f6", ptext="#414d5c",
         items=[("cfn", "CloudFormation", "6 stacks"),
                ("vpc", "VPC", "private subnets"),
                ("iam", "IAM", "execution roles"),
                ("s3", "S3", "data + grants"),
                ("catalog", "Service Catalog", "self-service"),
                ("sagemaker", "SageMaker AI", "Studio domain"),
                ("notebook", "JupyterLab", "space per user"),
                ("glue", "Glue", "Data Catalog"),
                ("athena", "Athena", "workgroup")]),
    dict(n="2", name="DATA PREP", sub="datasets & prompts", lab="Lab 2",
         persona="Data Engineer", colour="#0972D3", tint="#EAF2FB", ptint="#f2f4f6", ptext="#414d5c",
         items=[("s3", "S3", "source data"),
                ("sagemaker", "Processing job", "2B"),
                ("emr", "EMR", "Spark · 2C / 2D"),
                ("canvas", "Canvas", "no-code · 2E"),
                ("bucketobj", "S3 Tables", "Iceberg · 2F"),
                ("glue", "Glue", "table schemas"),
                ("athena", "Athena", "time travel"),
                ("sagemaker", "MLflow", "prompt registry · 2A")]),
    dict(n="3", name="MODEL BUILD", sub="train · evaluate · register", lab="Lab 3",
         persona="Data Scientist", colour="#7D3AC1", tint="#F3EBFB", ptint="#f2f4f6", ptext="#414d5c",
         items=[("athena", "Athena", "read baselines"),
                ("s3", "S3", "train / test JSONL"),
                ("train", "Training job", "XGBoost · 3A"),
                ("sagemaker", "JumpStart", "Llama 3.2 3B · 3B"),
                ("sagemaker", "MLflow", "experiments · metrics"),
                ("model", "Model Registry", "package + card · 3C")]),
    dict(n="4", name="MODEL DEPLOY", sub="CI/CD to endpoints", lab="Lab 4",
         persona="ML Engineer / Gov Officer", colour="#0F8B5F", tint="#E8F6EF", ptint="#eaf4ef", ptext="#0d5c42",
         items=[("model", "Approval gate", "Approved status"),
                ("GHA", "GitHub Actions", "build + deploy"),
                ("sagemaker", "Endpoint", "real-time inference"),
                ("sqs", "SQS", "capture queue"),
                ("iam", "IAM", "sqs:SendMessage")]),
    dict(n="5", name="MONITORING", sub="observe · govern · explain", lab="Lab 5",
         persona="Ops / Gov Officer", colour="#C2571A", tint="#FDF0E6", ptint="#fdf3ec", ptext="#9c4615",
         items=[("cloudwatch", "CloudWatch", "metrics 5A · logs 5B"),
                ("cloudtrail", "CloudTrail", "API audit · 5C"),
                ("lambda", "Lambda", "capture logger"),
                ("glue", "Glue", "monitoring tables"),
                ("athena", "Athena", "drift queries · 5D"),
                ("sagemaker", "MLflow", "drift verdicts · 5F"),
                ("quick", "Amazon Quick", "dashboard · 5E")]),
]

def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


for _st in STAGES:
    for _k in ("name", "sub", "persona", "lab"):
        _st[_k] = esc(_st[_k])
    _st["items"] = [(k, esc(a), esc(b)) for k, a, b in _st["items"]]

W = 1320
TITLE_H = 78
BAND_H = 122
GAP = 14
BAND_X = 52                    # leaves a clear lane at x<52 for the feedback loop
BAND_W = W - 20 - BAND_X
ICON = 56
SLOT = 108

CIRCLE_CX = BAND_X + 36
LABEL_X = BAND_X + 64
ICON_X0 = BAND_X + 232         # icons left-aligned so stages form a grid

band_tops = [TITLE_H + i * (BAND_H + GAP) for i in range(len(STAGES))]
bands_end = band_tops[-1] + BAND_H
loop_y = bands_end + 10
foot_y = loop_y + 44
H = foot_y + 66

out = []
out.append(f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
           f'width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="Helvetica, Arial, sans-serif">')
out.append("  <defs>")
out.append(f"    {SYMBOLS}")
out.append('    <marker id="arr" markerWidth="9" markerHeight="7" refX="8" refY="3.5" orient="auto">'
           '<path d="M0,0 L9,3.5 L0,7 z" fill="#C2571A"/></marker>')
out.append("  </defs>")
out.append(f'  <rect width="{W}" height="{H}" fill="#ffffff"/>')

out.append(f'  <text x="20" y="32" font-size="22" font-weight="bold" fill="#16191f">'
           f'GenAI / ML Standardization Workshop — Services by Lifecycle Stage</text>')
out.append(f'  <text x="20" y="54" font-size="12.5" fill="#5f6b7a">'
           f'Icon view · the AWS services you touch in each stage, Labs 1–5. '
           f'See architecture.svg for the detailed version.</text>')

for st, ty in zip(STAGES, band_tops):
    c = st["colour"]
    out.append(f'  <!-- stage {st["n"]} -->')
    out.append(f'  <g>')
    out.append(f'    <rect x="{BAND_X}" y="{ty}" width="{BAND_W}" height="{BAND_H}" rx="9" '
               f'fill="{st["tint"]}" stroke="{c}" stroke-width="1.5"/>')
    out.append(f'    <rect x="{BAND_X}" y="{ty}" width="7" height="{BAND_H}" rx="3.5" fill="{c}"/>')
    # stage number
    cy = ty + 44
    out.append(f'    <circle cx="{CIRCLE_CX}" cy="{cy}" r="19" fill="{c}"/>')
    out.append(f'    <text x="{CIRCLE_CX}" y="{cy+7}" font-size="19" font-weight="bold" fill="#fff" '
               f'text-anchor="middle">{st["n"]}</text>')
    out.append(f'    <text x="{LABEL_X}" y="{ty+34}" font-size="14.5" font-weight="bold" fill="{c}">{st["name"]}</text>')
    out.append(f'    <text x="{LABEL_X}" y="{ty+52}" font-size="10.2" fill="#5f6b7a">{st["sub"]}</text>')
    out.append(f'    <rect x="{LABEL_X}" y="{ty+62}" width="140" height="19" rx="4" fill="{st["ptint"]}" '
               f'stroke="{c}" stroke-width="0.9"/>')
    out.append(f'    <text x="{LABEL_X+70}" y="{ty+75}" font-size="9" font-weight="bold" fill="{st["ptext"]}" '
               f'text-anchor="middle">{st["persona"]}</text>')
    out.append(f'    <text x="{LABEL_X}" y="{ty+104}" font-size="11.5" font-weight="bold" fill="{c}">{st["lab"]}</text>')

    items = st["items"]
    x0 = ICON_X0
    iy = ty + 26
    for j, (key, cap1, cap2) in enumerate(items):
        cx = x0 + j * SLOT + SLOT / 2
        ix = cx - ICON / 2
        if key == "GHA":
            # Not an AWS service: the icon terms forbid using an AWS product
            # icon to stand for something else, so this gets a neutral tile.
            out.append(f'    <rect x="{ix:.1f}" y="{iy}" width="{ICON}" height="{ICON}" rx="6" '
                       f'fill="#24292f"/>')
            out.append(f'    <text x="{cx:.1f}" y="{iy+26}" font-size="9.5" font-weight="bold" fill="#fff" '
                       f'text-anchor="middle">non-AWS</text>')
            out.append(f'    <text x="{cx:.1f}" y="{iy+40}" font-size="9.5" font-weight="bold" fill="#fff" '
                       f'text-anchor="middle">CI/CD</text>')
        else:
            if ICONS[key][2]:
                out.append(f'    <rect x="{ix:.1f}" y="{iy}" width="{ICON}" height="{ICON}" '
                           f'fill="#ffffff" stroke="#01A88D" stroke-width="1.3"/>')
                pad = 6
                out.append(f'    <use xlink:href="#ic-{key}" x="{ix+pad:.1f}" y="{iy+pad}" '
                           f'width="{ICON-2*pad}" height="{ICON-2*pad}"/>')
            else:
                out.append(f'    <use xlink:href="#ic-{key}" x="{ix:.1f}" y="{iy}" '
                           f'width="{ICON}" height="{ICON}"/>')
        out.append(f'    <text x="{cx:.1f}" y="{iy+ICON+15}" font-size="9.8" font-weight="bold" '
                   f'fill="#16191f" text-anchor="middle">{cap1}</text>')
        out.append(f'    <text x="{cx:.1f}" y="{iy+ICON+27}" font-size="9" fill="#5f6b7a" '
                   f'text-anchor="middle">{cap2}</text>')
    out.append("  </g>")

# stage-to-stage chevrons, drawn in the gaps between bands
for _ty in band_tops[1:]:
    _gy = _ty - GAP / 2
    out.append(f'  <path d="M{CIRCLE_CX-7},{_gy-4:.1f} L{CIRCLE_CX},{_gy+4:.1f} L{CIRCLE_CX+7},{_gy-4:.1f}" '
               f'fill="none" stroke="#9aa7b4" stroke-width="2" stroke-linecap="round"/>')

# feedback loop: stage 5 back into stage 2, routed outside the bands
LANE = 30
S2_CY = band_tops[1] + BAND_H / 2
out.append(f'  <path d="M{W-60},{bands_end} L{W-60},{loop_y+16} L{LANE},{loop_y+16} '
           f'L{LANE},{S2_CY:.0f} L{BAND_X-3},{S2_CY:.0f}" '
           f'fill="none" stroke="#C2571A" stroke-width="1.6" stroke-dasharray="6,3" marker-end="url(#arr)"/>')
out.append(f'  <rect x="{W/2-140:.0f}" y="{loop_y+6}" width="280" height="20" rx="4" fill="#fff" '
           f'stroke="#C2571A" stroke-dasharray="3,2"/>')
out.append(f'  <text x="{W/2:.0f}" y="{loop_y+20}" font-size="10.2" fill="#C2571A" text-anchor="middle">'
           f'drift detected → re-prep data &amp; retrain</text>')

# footer / legend
out.append(f'  <g transform="translate({BAND_X},{foot_y})">')
out.append(f'    <rect width="{BAND_W}" height="56" rx="7" fill="#f7f8fa" stroke="#d5dbdb"/>')
out.append(f'    <text x="12" y="18" font-size="10.4" font-weight="bold" fill="#414d5c">LEGEND</text>')
out.append(f'    <text x="72" y="18" font-size="10.2" fill="#414d5c">'
           f'Filled square = AWS service icon · white square with teal border = AWS resource icon '
           f'(a specific capability of the service) · dark tile = non-AWS tool</text>')
out.append(f'    <text x="12" y="34" font-size="10.2" fill="#414d5c">'
           f'SageMaker AI appears in several stages because the workshop uses several of its '
           f'capabilities: Studio, Processing, Training, JumpStart, managed MLflow and Model Registry.</text>')
out.append(f'    <text x="12" y="49" font-size="9.6" fill="#5f6b7a">'
           f'Icons are the official AWS Architecture Icons (07/31/2026 release, aws.amazon.com/architecture/icons), '
           f'reproduced unmodified at uniform scale. AWS and its service icons are trademarks of Amazon.com, Inc. or its affiliates.</text>')
out.append("  </g>")
out.append("</svg>")

_default = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "images", "architecture-icons.svg")
dest = sys.argv[1] if len(sys.argv) > 1 else _default
with open(dest, "w", encoding="utf-8") as fh:
    fh.write("\n".join(out) + "\n")
print(f"wrote {dest} ({os.path.getsize(dest)} bytes) · {W}x{H}")
