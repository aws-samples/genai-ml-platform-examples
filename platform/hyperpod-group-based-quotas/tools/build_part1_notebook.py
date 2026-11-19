#!/usr/bin/env python3
"""Generate notebooks/part1-iam-mode.ipynb, the companion notebook for Part 1.

Run from anywhere: python tools/build_part1_notebook.py

IAM-mode validation of the full chain the blog post describes:

    group claim -> provisioning Lambda -> user profile -> execution role
      -> EKS access entry -> namespace -> Kueue queue -> compute quota

The provisioning function is invoked with the normalized request a SAML front
end would produce after validating an assertion: {"user": ..., "groups": [...]}.
Configuration is read from the CloudFormation stacks, so nothing is pasted.
"""

import json
from pathlib import Path

cells = []


def _id(prefix):
    return f"{prefix}-{len(cells):02d}"


def md(text):
    cells.append({"cell_type": "markdown", "id": _id("md"), "metadata": {},
                  "source": text.strip("\n")})


def code(text):
    cells.append({"cell_type": "code", "id": _id("code"), "execution_count": None,
                  "metadata": {}, "outputs": [], "source": text.strip("\n")})


md(r"""
# Validate in IAM mode: group claim to HyperPod quota

Proves that a user's group membership, and nothing else, decides which compute quota their work consumes.

The provisioning Lambda is called with the request a SAML front end produces after validating an assertion:

```json
{"user": "alice@corp.example.com", "groups": ["validate-search-ranking", "all-engineering"]}
```

Everything downstream of signature validation is real: the mapping lookup, the user profile, the execution role, the EKS access entry, the namespace, the Kueue queue and the compute quota.

| Section | Proves |
|---|---|
| 2 | Both teams have a quota, a namespace and a bound role |
| 3 | Group claims produce the right profile, and edge cases are refused |
| 4 | Sign-in: the user reaches Studio as themselves, and only their own profile |
| 5 | The chain from profile to quota, read from the live resources |
| 6 | A user's work lands in their team's quota and nowhere else |
| 7 | Quota limits, borrowing, and reclaim when the lender needs capacity back |
| 8 | Hard limits with lending and borrowing switched off |
| 9 | Studio offers only the team's namespace (manual) |
| 10 | Findings |
| 11 | Clean up (off by default) |

Requires `hpq-automation` deployed with `ValidationPrincipalArn` set, and run as that principal.
""")

md("## 1. Configuration and helpers")

code(r'''
import json, os, subprocess, tempfile, time
import boto3

REGION           = os.environ.get("AWS_REGION", "us-west-2")   # set AWS_REGION before starting Jupyter
AUTOMATION_STACK = "hpq-automation"
HYPERPOD_STACK   = "hpq-iam"

cfn = boto3.client("cloudformation", region_name=REGION)
def outputs(stack):
    o = cfn.describe_stacks(StackName=stack)["Stacks"][0]["Outputs"]
    return {x["OutputKey"]: x["OutputValue"] for x in o}

auto, hp = outputs(AUTOMATION_STACK), outputs(HYPERPOD_STACK)

EKS_CLUSTER    = hp["EksClusterName"]
HP_CLUSTER_ARN = hp["HyperPodClusterArn"]
DOMAIN_ID      = hp["StudioDomainId"]
FUNCTION       = auto["ProvisioningFunctionName"]
SIGNIN         = auto["SignInFunctionName"]
INSTANCE_TYPE  = "ml.m5.2xlarge"

TEAMS = {
    "validate-search-ranking":  {"role": auto["TeamARoleArn"], "namespace": auto["TeamANamespace"]},
    "validate-fraud-detection": {"role": auto["TeamBRoleArn"], "namespace": auto["TeamBNamespace"]},
}
for name, t in TEAMS.items():
    t["team"], t["quotaName"], t["queue"] = name, f"{name}-quota", f"{t['namespace']}-localqueue"

sagemaker = boto3.client("sagemaker", region_name=REGION)
eks       = boto3.client("eks",       region_name=REGION)
sts       = boto3.client("sts",       region_name=REGION)
lam       = boto3.client("lambda",    region_name=REGION)

findings = {}

def assume_env(role_arn, session):
    c = sts.assume_role(RoleArn=role_arn, RoleSessionName=session)["Credentials"]
    return {"AWS_ACCESS_KEY_ID": c["AccessKeyId"], "AWS_SECRET_ACCESS_KEY": c["SecretAccessKey"],
            "AWS_SESSION_TOKEN": c["SessionToken"], "AWS_DEFAULT_REGION": REGION}

def kubeconfig_for(env_extra=None):
    path = tempfile.mktemp(suffix=".kubeconfig")
    env = {**os.environ, **(env_extra or {}), "KUBECONFIG": path}
    r = subprocess.run(["aws", "eks", "update-kubeconfig", "--name", EKS_CLUSTER, "--region", REGION],
                       env=env, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr)
    return path

def kubectl(args, kc, env_extra=None, stdin=None):
    env = {**os.environ, **(env_extra or {}), "KUBECONFIG": kc}
    return subprocess.run(["kubectl", *args], env=env, capture_output=True, text=True, input=stdin)

def kjson(args):
    r = kubectl([*args, "-o", "json"], admin_kc)
    return json.loads(r.stdout) if r.returncode == 0 else None

admin_kc = kubeconfig_for()
print("caller :", sts.get_caller_identity()["Arn"])
print("cluster:", HP_CLUSTER_ARN)
print("domain :", DOMAIN_ID, " function:", FUNCTION)
''')

md(r"""
## 2. Make sure both teams exist

Per-team resources, which the post puts in infrastructure as code: a compute quota, which creates the namespace, and the execution role's access entry with its five policy associations. Idempotent, so it reuses anything already present.
""")

code(r'''
NAMESPACE_SCOPED = ["AmazonSagemakerHyperpodTrainingPolicy",
                    "AmazonSagemakerHyperpodInferencePolicy",
                    "AmazonSagemakerHyperpodSpacePolicy"]
POLICY = "arn:aws:eks::aws:cluster-access-policy/"

def existing_quota(name):
    for q in sagemaker.list_compute_quotas(ClusterArn=HP_CLUSTER_ARN)["ComputeQuotaSummaries"]:
        if q["Name"] == name and q["Status"] not in ("Deleted", "Deleting", "DeleteFailed"):
            return q["ComputeQuotaId"]

def ensure_team(t):
    qid = existing_quota(t["quotaName"])
    if not qid:
        qid = sagemaker.create_compute_quota(
            Name=t["quotaName"], ClusterArn=HP_CLUSTER_ARN,
            ComputeQuotaTarget={"TeamName": t["team"], "FairShareWeight": 50},
            ComputeQuotaConfig={
                "ComputeQuotaResources": [{"InstanceType": INSTANCE_TYPE, "Count": 1}],
                "ResourceSharingConfig": {"Strategy": "LendAndBorrow", "BorrowLimit": 50},
                "PreemptTeamTasks": "LowerPriority"},
            ActivationState="Enabled",
            Tags=[{"Key": "ADGroup", "Value": t["team"]}],
        )["ComputeQuotaId"]
        print(f"created quota {t['quotaName']} {qid}")
    else:
        print(f"reusing quota {t['quotaName']} {qid}")
    t["quotaId"] = qid

    for _ in range(60):   # namespace appears a few seconds after the quota
        if kubectl(["get", "ns", t["namespace"]], admin_kc).returncode == 0:
            break
        time.sleep(2)
    else:
        raise RuntimeError(f"{t['namespace']} never appeared")

    try:
        eks.create_access_entry(clusterName=EKS_CLUSTER, principalArn=t["role"], type="STANDARD")
    except eks.exceptions.ResourceInUseException:
        pass
    for p in NAMESPACE_SCOPED:
        eks.associate_access_policy(clusterName=EKS_CLUSTER, principalArn=t["role"], policyArn=POLICY + p,
                                    accessScope={"type": "namespace", "namespaces": [t["namespace"]]})
    eks.associate_access_policy(clusterName=EKS_CLUSTER, principalArn=t["role"],
                                policyArn=POLICY + "AmazonSagemakerHyperpodSpaceTemplatePolicy",
                                accessScope={"type": "namespace", "namespaces": ["jupyter-k8s-shared", "jupyter-k8s-system"]})
    eks.associate_access_policy(clusterName=EKS_CLUSTER, principalArn=t["role"],
                                policyArn=POLICY + "AmazonSagemakerHyperpodUserClusterPolicy",
                                accessScope={"type": "cluster"})

for t in TEAMS.values():
    ensure_team(t)

# Kueue applies new quotas asynchronously
for _ in range(30):
    cqs = [kjson(["get", "clusterqueue", f"{t['namespace']}-clusterqueue"]) for t in TEAMS.values()]
    if all(cqs):
        break
    time.sleep(2)
for cq in cqs:
    cpu = [r for r in cq["spec"]["resourceGroups"][0]["flavors"][0]["resources"] if r["name"] == "cpu"][0]
    print(f"{cq['metadata']['name']:52} cohort={cq['spec'].get('cohortName')} "
          f"cpu nominal={cpu['nominalQuota']} borrowLimit={cpu.get('borrowingLimit')}")
''')

md(r"""
## 3. Provision users from group claims

Each case is a request the SAML front end would send. The table in DynamoDB is the only place the group-to-team mapping lives.

| User | Groups in the claim | Expected |
|---|---|---|
| alice | `validate-search-ranking`, `all-engineering` | profile with team A's role. The unmapped group is ignored |
| bob | `validate-fraud-detection` | profile with team B's role |
| carol | both team groups | refused as a conflict, because a user holds one profile per domain |
| dave | `all-engineering` | no profile, because no group is mapped |
| erin | `Validate-Search-Ranking` | no profile. The match is exact, so a case mismatch fails silently |
| alice, again | same as before | `exists`, so sign-in is idempotent |
""")

code(r'''
def provision(user, groups):
    r = lam.invoke(FunctionName=FUNCTION, Payload=json.dumps({"user": user, "groups": groups}).encode())
    body = json.loads(r["Payload"].read())
    if r.get("FunctionError"):
        raise RuntimeError(body)
    return body

A, B = TEAMS["validate-search-ranking"], TEAMS["validate-fraud-detection"]
CASES = [
    ("alice@corp.example.com", ["validate-search-ranking", "all-engineering"], "created",    A),
    ("bob@corp.example.com",   ["validate-fraud-detection"],                   "created",    B),
    ("carol@corp.example.com", ["validate-search-ranking", "validate-fraud-detection"], "conflict", None),
    ("dave@corp.example.com",  ["all-engineering"],                            "no-mapping", None),
    ("erin@corp.example.com",  ["Validate-Search-Ranking"],                    "no-mapping", None),
    ("alice@corp.example.com", ["validate-search-ranking", "all-engineering"], "exists",     A),
]

results = []
for user, groups, expect, team in CASES:
    out = provision(user, groups)
    status = out["status"]
    # A re-run after a previous run finds the profiles already there
    ok = status == expect or (expect == "created" and status == "exists")
    if team:
        ok = ok and out.get("executionRoleArn") == team["role"]
    results.append({"user": user, "groups": groups, "expected": expect, "got": status, "ok": ok,
                    "role": out.get("executionRoleArn"), "detail": out.get("teams")})
    print(f"{'PASS' if ok else 'FAIL'}  {user:24} {expect:10} -> {status:10} "
          f"{(out.get('executionRoleArn') or '').split('/')[-1] or out.get('teams') or ''}")

findings["provisioning"] = results
assert all(r["ok"] for r in results), "a provisioning case did not behave as expected"

USERS = {}
for user, team in [("alice@corp.example.com", A), ("bob@corp.example.com", B)]:
    name = user.replace("@", "-").replace(".", "-")
    p = sagemaker.describe_user_profile(DomainId=DOMAIN_ID, UserProfileName=name)
    tags = {x["Key"]: x["Value"] for x in sagemaker.list_tags(ResourceArn=p["UserProfileArn"])["Tags"]}
    USERS[user.split("@")[0]] = {"profile": name, "role": p["UserSettings"]["ExecutionRole"]}
    print(f"\n{name}\n  role : {p['UserSettings']['ExecutionRole']}"
          f"\n  mode : {p['UserSettings'].get('StudioWebPortalSettings')}\n  tags : {tags}")
''')

md(r"""
## 4. Sign-in: the user arrives as themselves

In IAM mode the identity inside Studio comes from the IAM session that creates the presigned URL. If a shared component created URLs under its own role, every user would arrive with the same name, and teammates who share an execution role could not be told apart.

The sign-in function fixes this the way the post describes. It provisions the profile, assumes a dedicated role with `RoleSessionName` set to the user and a `studiouserid` session tag, and creates the URL with those credentials. That role can only open a profile whose `studiouserid` tag matches its session tag.

The URL's token is a JWT, so we decode it and read the identity it carries. We do not open it.
""")

code(r'''
import base64

def sign_in(user, groups, request_profile=None):
    req = {"user": user, "groups": groups}
    if request_profile:
        req["requestProfile"] = request_profile   # simulate a front end asking for someone else
    r = lam.invoke(FunctionName=SIGNIN, Payload=json.dumps(req).encode())
    return json.loads(r["Payload"].read())

def token_claims(url):
    part = url.split("token=")[1].split(".")[1]
    return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))

signin = {}

ok = sign_in("alice@corp.example.com", ["validate-search-ranking"])
claims = token_claims(ok["url"])
signin["alice"] = {k: claims[k] for k in ("userProfileName", "executionRoleSessionName", "partnerAppUserIdentity")}
print("alice  ->", ok["status"], signin["alice"])
assert claims["executionRoleSessionName"] == USERS["alice"]["profile"], "Studio identity is not alice"

steal = sign_in("alice@corp.example.com", ["validate-search-ranking"], request_profile=USERS["bob"]["profile"])
signin["aliceAsBob"] = steal
print("alice asking for bob's profile ->", steal["status"])
print("   ", steal.get("error", "")[:260])
assert steal["status"] == "forbidden"

nobody = sign_in("dave@corp.example.com", ["all-engineering"])
signin["dave"] = nobody
print("dave (no mapped group) ->", nobody["status"], nobody["provisioning"]["status"])
assert nobody["status"] == "denied"

findings["signIn"] = signin
''')

md(r"""
## 5. Follow the chain from the profile, not from config

For each user, start from the user profile and read every hop from the live resource. Nothing here uses the team configuration from section 1.
""")

code(r'''
quotas = {q["ComputeQuotaId"]: q for q in
          sagemaker.list_compute_quotas(ClusterArn=HP_CLUSTER_ARN)["ComputeQuotaSummaries"]}

chains = {}
for who, u in USERS.items():
    role = u["role"]
    assoc = eks.list_associated_access_policies(clusterName=EKS_CLUSTER, principalArn=role)["associatedAccessPolicies"]
    training = [a for a in assoc if a["policyArn"].endswith("AmazonSagemakerHyperpodTrainingPolicy")][0]
    ns = training["accessScope"]["namespaces"][0]
    lq = kjson(["get", "localqueues", "-n", ns])["items"][0]
    cq = lq["spec"]["clusterQueue"]
    team = ns.removeprefix("hyperpod-ns-")
    quota = [q for q in quotas.values() if q.get("ComputeQuotaTarget", {}).get("TeamName") == team
             and q["Status"] not in ("Deleted", "Deleting")]
    quota = quota[0] if quota else sagemaker.describe_compute_quota(ComputeQuotaId=TEAMS[team]["quotaId"])
    qtags = {x["Key"]: x["Value"] for x in sagemaker.list_tags(ResourceArn=quota["ComputeQuotaArn"])["Tags"]}
    chains[who] = {"profile": u["profile"], "role": role.split("/")[-1], "namespace": ns,
                   "localQueue": lq["metadata"]["name"], "clusterQueue": cq,
                   "computeQuota": quota["Name"], "quotaADGroup": qtags.get("ADGroup")}
    print(f"\n{who}")
    for k, v in chains[who].items():
        print(f"  {k:13} {v}")

findings["chains"] = chains
assert chains["alice"]["quotaADGroup"] == "validate-search-ranking"
assert chains["bob"]["quotaADGroup"] == "validate-fraud-detection"
''')

md(r"""
## 6. Each user's work lands in their own team's quota

Act as each user the way Studio does with `USER_IDENTITY`: assume the profile's execution role with the user as the session name. Submit a small Kueue-managed Job to the user's namespace and read which ClusterQueue admitted it. Then try the other team's namespace.
""")

code(r'''
IMAGE = "public.ecr.aws/docker/library/busybox:latest"

def job_yaml(name, ns, queue, cpu="500m", seconds=60):
    return f"""
apiVersion: batch/v1
kind: Job
metadata:
  name: {name}
  namespace: {ns}
  labels: {{kueue.x-k8s.io/queue-name: {queue}}}
spec:
  backoffLimit: 0
  ttlSecondsAfterFinished: 600
  template:
    metadata:
      labels: {{kueue.x-k8s.io/queue-name: {queue}}}
    spec:
      restartPolicy: Never
      terminationGracePeriodSeconds: 0
      containers:
      - name: work
        image: {IMAGE}
        command: ["sleep", "{seconds}"]
        resources:
          requests: {{cpu: "{cpu}", memory: 256Mi}}
          limits:   {{cpu: "{cpu}", memory: 256Mi}}
"""

def as_user(who):
    u = USERS[who]
    env = assume_env(u["role"], u["profile"])   # session name = user, as USER_IDENTITY does
    return env, kubeconfig_for(env)

def workloads(ns):
    """Kueue workloads in ns, keyed by owning job name."""
    out = {}
    for w in (kjson(["get", "workloads", "-n", ns]) or {"items": []})["items"]:
        owner = (w["metadata"].get("ownerReferences") or [{}])[0].get("name")
        conds = {c["type"]: c for c in w.get("status", {}).get("conditions", [])}
        out[owner] = {
            "admitted": conds.get("Admitted", {}).get("status") == "True",
            "clusterQueue": (w.get("status", {}).get("admission") or {}).get("clusterQueue"),
            "evicted": conds.get("Evicted", {}).get("status") == "True",
            "preempted": conds.get("Preempted", {}).get("reason") if conds.get("Preempted", {}).get("status") == "True" else None,
            "pending_reason": conds.get("QuotaReserved", {}).get("message") if conds.get("QuotaReserved", {}).get("status") != "True" else None,
        }
    return out

attribution = {}
for who, other in [("alice", "bob"), ("bob", "alice")]:
    own_ns, other_ns = chains[who]["namespace"], chains[other]["namespace"]
    own_q = chains[who]["localQueue"]
    env, kc = as_user(who)
    ident = json.loads(subprocess.run(["aws", "sts", "get-caller-identity"], env={**os.environ, **env},
                                      capture_output=True, text=True).stdout)["Arn"]
    can_own = kubectl(["auth", "can-i", "create", "jobs.batch", "-n", own_ns], kc, env).stdout.strip()
    can_other = kubectl(["auth", "can-i", "create", "jobs.batch", "-n", other_ns], kc, env).stdout.strip()

    job = f"attr-{who}"
    r_own = kubectl(["apply", "-f", "-"], kc, env, stdin=job_yaml(job, own_ns, own_q))
    r_other = kubectl(["apply", "-f", "-"], kc, env,
                      stdin=job_yaml(f"attr-{who}-cross", other_ns, chains[other]["localQueue"]))

    wl = None
    for _ in range(30):
        wl = workloads(own_ns).get(job)
        if wl and wl["admitted"]:
            break
        time.sleep(2)

    attribution[who] = {"identity": ident, "canCreateJobsOwn": can_own, "canCreateJobsOther": can_other,
                        "ownSubmit": (r_own.stdout or r_own.stderr).strip(),
                        "admittedBy": wl and wl["clusterQueue"],
                        "expectedClusterQueue": chains[who]["clusterQueue"],
                        "crossSubmit": r_other.stderr.strip() or r_other.stdout.strip()}
    os.unlink(kc)

    a = attribution[who]
    print(f"\n{who}  as {ident}")
    print(f"  can-i create jobs in {own_ns:40} {can_own}")
    print(f"  can-i create jobs in {other_ns:40} {can_other}")
    print(f"  own submit   : {a['ownSubmit']}")
    print(f"  admitted by  : {a['admittedBy']}   (expected {a['expectedClusterQueue']})")
    print(f"  cross submit : {a['crossSubmit']}")

    assert ident.endswith("/" + USERS[who]["profile"]), "session name did not carry the user"
    assert can_own == "yes" and can_other.startswith("no")
    assert a["admittedBy"] == a["expectedClusterQueue"], "work was charged to the wrong quota"
    assert r_other.returncode != 0 and "forbidden" in r_other.stderr.lower()

findings["attribution"] = attribution
for who in USERS:
    kubectl(["delete", "job", f"attr-{who}", "-n", chains[who]["namespace"], "--ignore-not-found",
             "--cascade=foreground", "--wait=false"], admin_kc)
''')

md(r"""
## 7. Quota limits, borrowing and reclaim

Each team's ClusterQueue has a CPU nominal quota of 8 and a borrowing limit of 4. Both are derived from one `ml.m5.2xlarge` in its compute quota. Jobs request 2 CPU each, so:

1. **Alice submits 7 jobs (14 CPU).** Expect her team's usage to reach 12 CPU: 8 on her own quota plus 4 borrowed from bob's idle capacity, the borrowing limit. The rest is held.
2. **Bob submits 4 jobs (8 CPU), his full nominal quota.** Bob's team lent 4 CPU to alice. Expect Kueue to reclaim it by evicting alice's borrowed jobs, then admit all 4 of bob's.

Checks compare CPU in use against the quota rather than counting jobs, because anything else the team is running, such as a Space, counts against the same quota.

This measures Kueue admission, which is the quota mechanism. Physical placement is separate. The template sets `ThreadsPerCore: 1`, so each 8-vCPU node exposes only 3.92 allocatable CPU, while task governance sizes the quota at 8 CPU per instance. Many admitted pods will therefore sit `Pending` on capacity. `waitForPodsReady` is disabled on this cluster, so that does not affect admission.
""")

code(r'''
JOB_CPU, ALICE_JOBS, BOB_JOBS = "2", 7, 4
SCREENSHOT_PAUSE = 0   # seconds to wait after phase 1, e.g. 300 to capture the console while alice is borrowing

def submit(who, n, prefix):
    env, kc = as_user(who)
    ns, q = chains[who]["namespace"], chains[who]["localQueue"]
    for i in range(n):
        r = kubectl(["apply", "-f", "-"], kc, env, stdin=job_yaml(f"{prefix}-{i}", ns, q, cpu=JOB_CPU, seconds=1800))
        assert r.returncode == 0, r.stderr
    os.unlink(kc)

def cq_usage(cq):
    s = kjson(["get", "clusterqueue", cq]).get("status", {})
    for f in s.get("flavorsUsage", []):
        for r in f["resources"]:
            if r["name"] == "cpu":
                return {"cpuUsed": r.get("total"), "cpuBorrowed": r.get("borrowed", "0")}
    return {}

def snapshot(label, prefix="load-"):
    snap = {}
    for who in USERS:
        ns, cq = chains[who]["namespace"], chains[who]["clusterQueue"]
        wls = {k: v for k, v in workloads(ns).items() if k and k.startswith(prefix)}
        pods = kjson(["get", "pods", "-n", ns, "-l", "kueue.x-k8s.io/queue-name"])["items"]
        snap[who] = {
            "admitted": sum(w["admitted"] for w in wls.values()),
            "held": sum(not w["admitted"] for w in wls.values()),
            "evictedOrPreempted": sorted(k for k, w in wls.items() if w["evicted"] or w["preempted"]),
            "podsRunning": sum(p["status"]["phase"] == "Running" for p in pods if p["metadata"]["name"].startswith(prefix)),
            **cq_usage(cq),
        }
        held_msgs = {w["pending_reason"] for w in wls.values() if not w["admitted"] and w["pending_reason"]}
        snap[who]["heldReason"] = sorted(held_msgs)[:1]
    print(f"\n--- {label}")
    for who, s in snap.items():
        print(f"  {who:6} admitted={s['admitted']} held={s['held']} cpuUsed={s.get('cpuUsed')} "
              f"borrowed={s.get('cpuBorrowed')} podsRunning={s['podsRunning']} evicted={s['evictedOrPreempted']}")
        for m in s["heldReason"]:
            print(f"         held because: {m[:220]}")
    return snap

def settle(seconds=60):
    time.sleep(seconds)

def cpu(v):
    v = str(v or "0")
    return float(v[:-1]) / 1000 if v.endswith("m") else float(v)

def baseline():
    """CPU already charged to each team before the test, e.g. a Space a user opened."""
    b = {who: cpu(cq_usage(chains[who]["clusterQueue"]).get("cpuUsed")) for who in USERS}
    for who, v in b.items():
        print(f"  {who:6} already using {v:g} CPU of its quota before the test")
    return b

NOMINAL, BORROW = 8, 4

print("baseline:")
base = baseline()
submit("alice", ALICE_JOBS, "load-alice")
settle()
phase1 = snapshot("phase 1: alice submits 7 x 2 CPU, bob idle")
if SCREENSHOT_PAUSE:
    print(f"\npausing {SCREENSHOT_PAUSE}s for screenshots; alice is borrowing now")
    time.sleep(SCREENSHOT_PAUSE)

submit("bob", BOB_JOBS, "load-bob")
settle(90)
phase2 = snapshot("phase 2: bob submits 4 x 2 CPU")

findings["quota"] = {"phase1": phase1, "phase2": phase2}

p1a, p2a, p2b = phase1["alice"], phase2["alice"], phase2["bob"]
checks = {
    f"alice used {NOMINAL}+{BORROW} CPU while bob was idle":   cpu(p1a.get("cpuUsed")) == NOMINAL + BORROW,
    f"alice borrowed exactly {BORROW} CPU":                    cpu(p1a.get("cpuBorrowed")) == BORROW,
    "alice's excess was held, not admitted":                    p1a["held"] >= 1,
    "bob admitted all 4 once he needed his quota":              p2b["admitted"] == 4,
    "alice's borrowed jobs were evicted to make room":          len(p2a["evictedOrPreempted"]) >= 1,
    f"alice back to her nominal {NOMINAL} CPU, borrowing 0":    cpu(p2a.get("cpuUsed")) == NOMINAL and cpu(p2a.get("cpuBorrowed")) == 0,
}
print()
for k, v in checks.items():
    print(f"{'PASS' if v else 'FAIL'}  {k}")
findings["quota"]["checks"] = checks
''')

md(r"""
## 8. Hard limits: no lending, no borrowing

Same users and same jobs, with both quotas switched to `DontLend` and `BorrowLimit: 0`. Nobody lends, so nobody can borrow, and each team's allocation becomes an absolute cap even while the other team's capacity sits idle. Compare with section 6, where alice ran 12 CPU on an 8 CPU allocation.

1. **Alice submits 7 jobs (14 CPU) while bob is idle.** Expect her team's usage to stop at exactly 8 CPU, with the rest held and nothing borrowed.
2. **Bob submits 6 jobs (12 CPU) while alice is saturated.** Expect bob to stop at 8 CPU with 2 held, and alice to keep everything she had. Nothing is reclaimed, because nothing was borrowed.

Checks compare CPU in use against the cap rather than counting jobs, because anything else the team is already running, such as a Space a user opened in Studio, counts against the same quota. The baseline line shows it.

The section restores `LendAndBorrow` at the end so section 6 still holds on a re-run. Set `RESTORE_SHARING = False` to keep the hard limits in place, for example to take screenshots.
""")

code(r'''
RESTORE_SHARING = True

def set_sharing(strategy, borrow_limit):
    for t in TEAMS.values():
        q = sagemaker.describe_compute_quota(ComputeQuotaId=t["quotaId"])
        cfg = q["ComputeQuotaConfig"]
        cfg["ResourceSharingConfig"] = {"Strategy": strategy, "BorrowLimit": borrow_limit}
        sagemaker.update_compute_quota(ComputeQuotaId=t["quotaId"], TargetVersion=q["ComputeQuotaVersion"],
                                       ComputeQuotaConfig=cfg)
    # Wait until Kueue reflects the new limits on both ClusterQueues
    want = "0" if strategy == "DontLend" else str(BORROW)
    for _ in range(60):
        lims = {}
        for t in TEAMS.values():
            cq = kjson(["get", "clusterqueue", f"{t['namespace']}-clusterqueue"])
            cpu = [r for r in cq["spec"]["resourceGroups"][0]["flavors"][0]["resources"] if r["name"] == "cpu"][0]
            lims[t["team"]] = {"nominal": cpu["nominalQuota"], "borrowingLimit": cpu.get("borrowingLimit"),
                               "lendingLimit": cpu.get("lendingLimit")}
        if all(l["borrowingLimit"] == want for l in lims.values()):
            return lims
        time.sleep(5)
    return lims

def clear_jobs(prefix):
    for who in USERS:
        ns = chains[who]["namespace"]
        names = [j["metadata"]["name"] for j in kjson(["get", "jobs", "-n", ns])["items"]
                 if j["metadata"]["name"].startswith(prefix)]
        if names:
            kubectl(["delete", "jobs", "-n", ns, *names, "--wait=false"], admin_kc)
    for _ in range(60):
        if not any(k and k.startswith(prefix) for who in USERS for k in workloads(chains[who]["namespace"])):
            return
        time.sleep(3)

clear_jobs("load-")                     # section 6's borrowing jobs
lims = set_sharing("DontLend", 0)
print("ClusterQueue CPU limits after switching to DontLend:")
for team, l in lims.items():
    print(f"  {team:26} nominal={l['nominal']} borrowingLimit={l['borrowingLimit']} lendingLimit={l['lendingLimit']}")

print("baseline:")
hard_base = baseline()
submit("alice", 7, "hard-alice")
settle()
hard1 = snapshot("hard phase 1: alice submits 7 x 2 CPU, bob idle", prefix="hard-")

submit("bob", 6, "hard-bob")
settle(90)
hard2 = snapshot("hard phase 2: bob submits 6 x 2 CPU while alice is saturated", prefix="hard-")

h1a, h2a, h2b = hard1["alice"], hard2["alice"], hard2["bob"]
hard_checks = {
    "both ClusterQueues show borrowingLimit=0":                 all(l["borrowingLimit"] == "0" for l in lims.values()),
    f"alice capped at {NOMINAL} CPU although bob was idle":     cpu(h1a.get("cpuUsed")) == NOMINAL and h1a["held"] >= 1,
    "alice borrowed nothing":                                   cpu(h1a.get("cpuBorrowed")) == 0,
    f"bob capped at {NOMINAL} CPU, excess held":                cpu(h2b.get("cpuUsed")) == NOMINAL and h2b["held"] == 2,
    "alice untouched when bob arrived, nothing evicted":        cpu(h2a.get("cpuUsed")) == NOMINAL and not h2a["evictedOrPreempted"],
}
print()
for k, v in hard_checks.items():
    print(f"{'PASS' if v else 'FAIL'}  {k}")
findings["hardLimits"] = {"limits": lims, "phase1": hard1, "phase2": hard2, "checks": hard_checks}

if RESTORE_SHARING:
    clear_jobs("hard-")
    restored = set_sharing("LendAndBorrow", 50)
    print("\nrestored LendAndBorrow:", restored)
''')

md(r"""
## 9. Studio shows only the team's namespace (manual)

Open the URL, choose **HyperPod**, and start creating a Space. The namespace selector should offer only `hyperpod-ns-validate-search-ranking`. Take the screenshot for the post here.

The URL comes from the sign-in function, so Studio knows you as `alice-corp-example-com`, the same identity section 4 decoded from the token.
""")

code(r'''
MINT_URL = False   # set True when you are ready to open it; the URL is a live sign-in token

if MINT_URL:
    url = sign_in("alice@corp.example.com", ["validate-search-ranking"])["url"]
    print("valid for 5 minutes. Do not save the notebook with this output:\n")
    print(url)
else:
    print("MINT_URL is False")
''')

md("## 10. Findings")

code(r'''
print(json.dumps(findings, indent=2, default=str)[:6000])
with open("iam-quota-findings.json", "w") as fh:
    json.dump(findings, fh, indent=2, default=str)
print("\nwritten to iam-quota-findings.json")
''')

md(r"""
## 11. Clean up

Off by default so you can take screenshots first. Set `RUN_CLEANUP = True` and run. Removes the load jobs and offboards the test users through the same function, `{"action": "remove"}`. With `DELETE_TEAMS = True` it also deletes the per-team resources from section 2: both compute quotas, which removes their namespaces, and both access entries. Do that before deleting the stacks.
""")

code(r'''
RUN_CLEANUP  = False
DELETE_TEAMS = True

if RUN_CLEANUP:
    for who in USERS:
        ns = chains[who]["namespace"]
        r = kubectl(["delete", "jobs", "-n", ns, "-l", "kueue.x-k8s.io/queue-name", "--wait=false"], admin_kc)
        print(r.stdout.strip() or r.stderr.strip())
    for user in ["alice@corp.example.com", "bob@corp.example.com"]:
        r = lam.invoke(FunctionName=FUNCTION, Payload=json.dumps({"action": "remove", "user": user}).encode())
        print(user, json.loads(r["Payload"].read()))
    if DELETE_TEAMS:
        for t in TEAMS.values():
            try:
                sagemaker.delete_compute_quota(ComputeQuotaId=t["quotaId"])
                print("deleted quota", t["quotaName"])
            except Exception as e:
                print("quota", t["quotaName"], "->", type(e).__name__, e)
            try:
                eks.delete_access_entry(clusterName=EKS_CLUSTER, principalArn=t["role"])
                print("deleted access entry for", t["team"])
            except eks.exceptions.ResourceNotFoundException:
                pass
        for t in TEAMS.values():
            for _ in range(36):
                if kubectl(["get", "ns", t["namespace"]], admin_kc).returncode != 0:
                    print("namespace gone:", t["namespace"])
                    break
                time.sleep(5)
else:
    print("RUN_CLEANUP is False, nothing deleted")
''')

notebook = {
    "cells": cells,
    "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                 "language_info": {"name": "python"}},
    "nbformat": 4, "nbformat_minor": 5,
}
out = Path(__file__).resolve().parent.parent / "notebooks" / "part1-iam-mode.ipynb"
with open(out, "w") as fh:
    json.dump(notebook, fh, indent=1)
print(f"wrote {out} with {len(cells)} cells")
