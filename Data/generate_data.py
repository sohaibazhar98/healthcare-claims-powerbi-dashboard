"""Generate a realistic, fully fictional large-group health plan dataset.

Tables: groups, plans, providers, members, enrollment (member months + premium), claims.
All names are invented. Service dates Jan 2024 - Sep 2026, data as of 2026-10-15.
"""
import sys
import numpy as np
import pandas as pd

OUT = sys.argv[1]
rng = np.random.default_rng(20261029)

MONTHS = pd.date_range("2024-01-01", "2026-08-01", freq="MS")
AS_OF = pd.Timestamp("2026-10-25")
AGE_REF = pd.Timestamp("2026-01-01")

# ---------------------------------------------------------------- plans
plans = pd.DataFrame([
    # id, name, type, deductible, oop, coins, util, premium base PMPM (2024)
    ("PL01", "Harborline HMO Standard", "HMO", 0, 4000, 0.10, 0.94, 540),
    ("PL02", "Harborline HMO Plus", "HMO", 0, 3000, 0.05, 0.98, 585),
    ("PL03", "Harborline PPO Choice", "PPO", 750, 5000, 0.20, 1.05, 610),
    ("PL04", "Harborline PPO Premier", "PPO", 250, 3500, 0.10, 1.13, 690),
    ("PL05", "Harborline EPO Select", "EPO", 500, 4500, 0.15, 1.00, 560),
    ("PL06", "Harborline HDHP + HSA", "HDHP", 3200, 7000, 0.10, 0.84, 455),
], columns=["PlanID", "PlanName", "PlanType", "Deductible", "OOPMax", "Coinsurance", "util", "base_prem"])

# ---------------------------------------------------------------- groups
industries = {
    "Healthcare": "Medical Partners", "Education": "Academy", "Manufacturing": "Manufacturing",
    "Technology": "Technologies", "Public Sector": "Public Authority", "Retail": "Retail Group",
    "Financial Services": "Financial", "Construction": "Builders", "Hospitality": "Hospitality",
    "Nonprofit": "Community Services", "Logistics": "Logistics", "Professional Services": "Consulting",
}
prefixes = ["Ridgeline", "Harborview", "Stonebridge", "Kestrel", "Bayfront", "Larkspur", "Ironleaf",
            "Silverbrook", "Redbud", "Northgate", "Westbury", "Eastwick", "Lakeshore", "Riverbend",
            "Oakmont", "Pinecrest", "Glenhaven", "Maple Run", "Fairhollow", "Brookfield", "Kingsley",
            "Copperline", "Tidewell", "Summit Grove", "Bluefin", "Wrenfield", "Ashford Lane",
            "Cobalt Bay", "Juniper", "Foxhall", "Granite Shore", "Meadowlark", "Halcyon"]
rng.shuffle(prefixes)
ind_names = list(industries)
N_GROUPS = 33
seg_sizes = ([("51-249", rng.integers(60, 230)) for _ in range(20)]
             + [("250-999", rng.integers(260, 640)) for _ in range(10)]
             + [("1,000+", rng.integers(1000, 1180)) for _ in range(3)])
rng.shuffle(seg_sizes)
rows = []
for i in range(N_GROUPS):
    ind = ind_names[i % len(ind_names)] if i < len(ind_names) else rng.choice(ind_names)
    seg, size = seg_sizes[i]
    rows.append(dict(
        GroupID=f"G{1001 + i}",
        GroupName=f"{prefixes[i]} {industries[ind]}",
        Industry=ind,
        State=rng.choice(["MD", "DC", "VA"], p=[0.62, 0.16, 0.22]),
        MarketSegment=seg,
        size=int(size),
        RenewalMonth=int(rng.choice([1, 7, 4, 10], p=[0.6, 0.2, 0.1, 0.1])),
        risk=float(np.exp(rng.normal(0, 0.17))),
        growth=float(rng.normal(0.025, 0.04)),
    ))
groups = pd.DataFrame(rows)
# industry risk tilt
ind_tilt = {"Construction": 1.07, "Manufacturing": 1.06, "Public Sector": 1.04, "Hospitality": 0.97,
            "Technology": 0.95, "Retail": 0.98, "Logistics": 1.03, "Healthcare": 1.01,
            "Education": 1.03, "Nonprofit": 1.0, "Financial Services": 0.96, "Professional Services": 0.96}
groups["risk"] *= groups["Industry"].map(ind_tilt)
# premium reflects risk only partially (credibility) -> loss ratios vary by group
groups["rate_adj"] = 1 + 0.55 * (groups["risk"] - 1) + rng.normal(0, 0.03, len(groups))

# effective / termination dates: most in force from 2024; 4 new-business groups; 2 lapses
groups["EffectiveDate"] = pd.Timestamp("2024-01-01")
groups["TermDate"] = pd.NaT
newbiz = groups.sample(4, random_state=7).index
for idx, d in zip(newbiz, ["2025-01-01", "2025-07-01", "2026-01-01", "2026-04-01"]):
    groups.loc[idx, "EffectiveDate"] = pd.Timestamp(d)
    groups.loc[idx, "RenewalMonth"] = pd.Timestamp(d).month
cand = groups.drop(newbiz).sort_values("risk", ascending=False)
lapse = cand.index[[0, 2]]  # two high-risk groups lapse at their 2026 renewal
groups.loc[lapse, "RenewalMonth"] = 1
groups.loc[lapse, "TermDate"] = pd.Timestamp("2025-12-31")
groups["GroupStatus"] = np.where(groups["TermDate"].notna(), "Terminated", "Active")

# plan offerings per group
offer = {}
for g in groups.itertuples():
    k = rng.choice([2, 3, 4], p=[0.3, 0.45, 0.25])
    base = ["PL03"] + list(rng.choice(["PL01", "PL02", "PL04", "PL05", "PL06"], size=k - 1, replace=False))
    offer[g.GroupID] = base

# ---------------------------------------------------------------- members
age_dist_by_ind = {"Technology": 36, "Hospitality": 33, "Retail": 35, "Public Sector": 45,
                   "Education": 43, "Manufacturing": 44, "Construction": 41}


def make_members(g, n, start, mid0):
    rel = rng.choice(["Subscriber", "Spouse", "Child"], size=n, p=[0.52, 0.17, 0.31])
    mean_age = age_dist_by_ind.get(g.Industry, 40)
    age = np.where(rel == "Child", rng.integers(0, 26, n),
                   np.clip(rng.normal(mean_age, 11, n), 21, 72)).astype(int)
    gender = np.where(rel == "Spouse", rng.choice(["F", "M"], n, p=[0.68, 0.32]),
                      rng.choice(["F", "M"], n, p=[0.52, 0.48]))
    bday = AGE_REF - pd.to_timedelta(age * 365.25 + rng.integers(0, 365, n), unit="D")
    plan_opts = offer[g.GroupID]
    w = np.array([{"PL01": 1.2, "PL02": 1.0, "PL03": 1.4, "PL04": 0.8, "PL05": 0.9, "PL06": 1.0}[p]
                  for p in plan_opts])
    plan = rng.choice(plan_opts, size=n, p=w / w.sum())
    return pd.DataFrame(dict(MemberID=[f"M{mid0 + i:06d}" for i in range(n)], GroupID=g.GroupID,
                             PlanID=plan, Relationship=rel, Gender=gender, BirthDate=bday.normalize(),
                             EnrollStart=start))


mem_frames, mid = [], 100001
for g in groups.itertuples():
    eff = g.EffectiveDate
    m0 = make_members(g, g.size, eff, mid); mid += g.size
    mem_frames.append(m0)
    # monthly hires to replace terms + growth
    active_est = g.size
    for m in MONTHS[MONTHS > eff]:
        if pd.notna(g.TermDate) and m > g.TermDate:
            break
        hires = rng.poisson(active_est * (0.011 + g.growth / 12))
        if hires:
            mh = make_members(g, hires, m, mid); mid += hires
            mem_frames.append(mh)
        active_est *= (1 + g.growth / 12)
members = pd.concat(mem_frames, ignore_index=True)

# terminations ~ 1.1%/month, plus group lapse
n = len(members)
term_after = rng.geometric(0.011, n)  # months until term
end = members["EnrollStart"].values.astype("datetime64[M]") + term_after.astype("timedelta64[M]")
end = pd.to_datetime(end) - pd.Timedelta(days=1)
members["EnrollEnd"] = end
gterm = members["GroupID"].map(groups.set_index("GroupID")["TermDate"])
members["EnrollEnd"] = np.where(gterm.notna() & (gterm < members["EnrollEnd"]), gterm, members["EnrollEnd"])
members["EnrollEnd"] = pd.to_datetime(members["EnrollEnd"])
members.loc[members["EnrollEnd"] > AS_OF, "EnrollEnd"] = pd.NaT

age = ((AGE_REF - members["BirthDate"]).dt.days / 365.25).astype(int)
members["Age"] = age
bands = [(0, 17, "0-17"), (18, 29, "18-29"), (30, 39, "30-39"), (40, 49, "40-49"), (50, 59, "50-59"), (60, 200, "60+")]
members["AgeBand"] = pd.cut(age, [-1, 17, 29, 39, 49, 59, 200], labels=[b[2] for b in bands]).astype(str)


def age_factor(a, gdr):
    f = np.select([a < 2, a < 18, a < 30, a < 40, a < 50, a < 60], [1.6, 0.55, 0.68, 0.92, 1.22, 1.72], 2.15)
    f = f * np.where((gdr == "F") & (a >= 18) & (a < 45), 1.25, 1.0)
    return f


members["af"] = age_factor(members["Age"].values, members["Gender"].values)

# ---------------------------------------------------------------- member months
mm_rows = []
starts = members["EnrollStart"].values.astype("datetime64[M]")
ends = members["EnrollEnd"].fillna(pd.Timestamp("2099-12-31")).values.astype("datetime64[M]")
for m in MONTHS:
    mv = np.datetime64(m, "M")
    act = np.where((starts <= mv) & (ends >= mv))[0]
    mm_rows.append(pd.DataFrame({"midx": act, "MonthStart": m}))
mm = pd.concat(mm_rows, ignore_index=True)
mm = mm.join(members[["MemberID", "GroupID", "PlanID", "Gender", "Age", "AgeBand", "af"]], on="midx")
gi = groups.set_index("GroupID")
pi = plans.set_index("PlanID")
mm["risk"] = mm["GroupID"].map(gi["risk"])
mm["util"] = mm["PlanID"].map(pi["util"])

# premium: base x age/gender rating x group rate adj x cumulative renewal increases
years_since = (mm["MonthStart"].dt.year - 2024) + 0  # placeholder
ren = mm["GroupID"].map(gi["RenewalMonth"])
# number of renewals passed since Jan 2024 for each row
n_ren = (mm["MonthStart"].dt.year - 2024) + (mm["MonthStart"].dt.month >= ren).astype(int) - (ren == 1).astype(int)
n_ren = n_ren.clip(lower=0)
incr = {gid: rng.normal(0.06, 0.018, 4) for gid in groups["GroupID"]}
# high-risk groups get bigger increases at renewal (experience rating)
for gid, r in gi["risk"].items():
    incr[gid] = incr[gid] + 0.05 * max(r - 1, 0)
cum = np.ones(len(mm))
gids = mm["GroupID"].values
nr = n_ren.values
for gid in groups["GroupID"]:
    sel = gids == gid
    c = np.concatenate([[1.0], np.cumprod(1 + incr[gid])])
    cum[sel] = c[nr[sel]]
rating = 0.30 + 0.70 * mm["af"].values  # rating curve flatter than cost curve (community-ish)
mm["Premium"] = (mm["PlanID"].map(pi["base_prem"]).values * rating
                 * mm["GroupID"].map(gi["rate_adj"]).values * cum).round(2)

enrollment = (mm.groupby(["MonthStart", "GroupID", "PlanID", "AgeBand"], as_index=False)
              .agg(MemberMonths=("MemberID", "size"), PremiumAmount=("Premium", "sum")))
enrollment["PremiumAmount"] = enrollment["PremiumAmount"].round(2)

# ---------------------------------------------------------------- providers
places = ["Northgate", "Westbury", "Eastwick", "Lakeshore", "Riverbend", "Oakmont", "Pinecrest", "Glenhaven",
          "Maple Run", "Fairhollow", "Brookfield", "Kingsley", "Harborview", "Ridgeline", "Stonebridge",
          "Bayfront", "Millcrest", "Cedar Hollow", "Ashby", "Willow Glen", "Hartwell", "Seabrook Point"]
surnames = ["Patel", "Nguyen", "Okafor", "Reyes", "Kim", "Johnson", "Abernathy", "Siddiqui", "Moreau",
            "Castillo", "Haddad", "Lindqvist", "Osei", "Brennan", "Tanaka", "Romero", "Whitfield", "Desai",
            "Kowalski", "Mensah", "Ferreira", "Albright", "Chaudhry", "Delgado", "Iverson", "Nakamura"]
specs = {"Family Medicine": 34, "Internal Medicine": 22, "Pediatrics": 16, "OB/GYN": 12, "Orthopedics": 14,
         "Cardiology": 10, "Dermatology": 8, "Behavioral Health": 20, "Gastroenterology": 8, "Oncology": 7,
         "Neurology": 7, "Physical Therapy": 12, "Endocrinology": 6, "Pulmonology": 6}
prov = []
pid = 1


def addp(name, ptype, spec, oon_p):
    global pid
    prov.append(dict(ProviderID=f"P{pid:04d}", ProviderName=name, ProviderType=ptype, Specialty=spec,
                     NetworkStatus="Out-of-Network" if rng.random() < oon_p else "In-Network",
                     State=rng.choice(["MD", "DC", "VA"], p=[0.66, 0.14, 0.20])))
    pid += 1


used = set()
for i in range(12):
    nm = f"{places[i]} {rng.choice(['Regional Medical Center', 'General Hospital', 'Medical Center'])}"
    addp(nm, "Hospital", "Acute Care Hospital", 0.0)
for spec, k in specs.items():
    for _ in range(k):
        while True:
            style = rng.integers(0, 3)
            if style == 0:
                nm = f"{rng.choice(places)} {spec} Associates"
            elif style == 1:
                nm = f"{rng.choice(surnames)} & {rng.choice(surnames)} {spec}"
            else:
                nm = f"{rng.choice(surnames)} {spec} Group"
            if nm not in used:
                used.add(nm); break
        addp(nm, "Physician Group", spec, 0.16)
for i in range(30):
    nm = f"{rng.choice(['Brightway', 'Corner', 'Neighborly', 'Greenleaf', 'Main Street'])} Pharmacy #{100 + i}"
    addp(nm, "Pharmacy", "Retail Pharmacy", 0.0)
addp("Harborline Mail-Order Pharmacy", "Pharmacy", "Mail-Order Pharmacy", 0.0)
addp("Harborline Specialty Pharmacy", "Pharmacy", "Specialty Pharmacy", 0.0)
for i in range(14):
    addp(f"{places[(i + 5) % len(places)]} Urgent Care", "Urgent Care", "Urgent Care", 0.05)
for i in range(16):
    addp(f"{places[(i + 3) % len(places)]} {rng.choice(['Imaging', 'Diagnostic Lab', 'Imaging & Lab'])}",
         "Imaging & Lab", "Imaging & Lab", 0.06)
for i in range(8):
    addp(f"{places[(i + 9) % len(places)]} Surgery Center", "Ambulatory Surgery Center", "Ambulatory Surgery", 0.05)
providers = pd.DataFrame(prov).drop_duplicates("ProviderName")

# ---------------------------------------------------------------- claims
TYPES = {
    #            freq/mo  mean allowed  sigma
    "Pharmacy": (0.29, 205, 1.25),
    "Professional": (0.23, 250, 0.85),
    "Outpatient": (0.072, 1950, 1.0),
    "Emergency": (0.016, 2650, 0.65),
    "Inpatient": (0.0062, 23500, 0.75),
}
DIAG = {
    "Pharmacy": {"Diabetes & Endocrine": 18, "Cardiovascular": 16, "Behavioral Health": 17, "Respiratory": 12,
                 "Musculoskeletal": 8, "Gastrointestinal": 7, "Oncology": 3, "Preventive & Wellness": 4,
                 "Neurology": 6, "Other": 9},
    "Professional": {"Preventive & Wellness": 22, "Musculoskeletal": 15, "Behavioral Health": 13, "Respiratory": 11,
                     "Cardiovascular": 7, "Diabetes & Endocrine": 6, "Injury": 7, "Gastrointestinal": 5,
                     "Maternity": 3, "Neurology": 4, "Oncology": 2, "Other": 5},
    "Outpatient": {"Musculoskeletal": 20, "Gastrointestinal": 15, "Oncology": 8, "Cardiovascular": 10, "Injury": 10,
                   "Neurology": 7, "Preventive & Wellness": 8, "Maternity": 4, "Respiratory": 5, "Other": 13},
    "Emergency": {"Injury": 30, "Respiratory": 15, "Gastrointestinal": 15, "Cardiovascular": 12,
                  "Behavioral Health": 7, "Neurology": 8, "Other": 13},
    "Inpatient": {"Maternity": 22, "Cardiovascular": 17, "Musculoskeletal": 14, "Gastrointestinal": 10,
                  "Oncology": 8, "Respiratory": 8, "Behavioral Health": 6, "Injury": 7, "Neurology": 4, "Other": 4},
}
DIAG_COST = {"Oncology": 2.6, "Preventive & Wellness": 0.6, "Cardiovascular": 1.25, "Musculoskeletal": 1.1,
             "Behavioral Health": 0.85, "Maternity": 1.0}
season_prof = {1: 1.12, 2: 1.10, 3: 1.06, 4: 1.0, 5: 0.98, 6: 0.95, 7: 0.92, 8: 0.95, 9: 1.0, 10: 1.02, 11: 1.0, 12: 0.93}
season_er = {1: 1.05, 2: 1.0, 3: 0.98, 4: 0.97, 5: 1.0, 6: 1.06, 7: 1.08, 8: 1.06, 9: 1.0, 10: 0.97, 11: 0.95, 12: 1.0}

mm_month = mm["MonthStart"].dt.month.values
trend_years = ((mm["MonthStart"] - pd.Timestamp("2024-01-01")).dt.days / 365.25).values
claim_frames = []
for ctype, (freq, mean, sig) in TYPES.items():
    seas = np.vectorize(season_er.get if ctype == "Emergency" else
                        (season_prof.get if ctype in ("Professional", "Outpatient") else (lambda m: 1.0)))(mm_month)
    util_trend = 1.03 ** trend_years  # utilization trend
    lam = freq * mm["af"].values * mm["risk"].values ** 0.7 * mm["util"].values * seas * util_trend
    if ctype == "Pharmacy":
        lam = lam * np.where(mm["Age"].values >= 40, 1.35, 0.8)
    cnt = rng.poisson(lam)
    idx = np.repeat(np.arange(len(mm)), cnt)
    c = mm.iloc[idx][["MemberID", "GroupID", "PlanID", "Gender", "Age", "MonthStart", "risk"]].reset_index(drop=True)
    c["ClaimType"] = ctype
    ty = trend_years[idx]
    # unit cost trend ~5%/yr (Rx 7%)
    ucost = (1.095 if ctype == "Pharmacy" else 1.065) ** ty
    mu = np.log(mean) - sig ** 2 / 2
    c["Allowed"] = np.exp(rng.normal(mu, sig, len(c))) * ucost * c["risk"].values ** 0.3
    claim_frames.append(c)
claims = pd.concat(claim_frames, ignore_index=True)

# catastrophic / high-cost episodes (drive high-cost claimants)
mem_years = mm.groupby(["MemberID", mm["MonthStart"].dt.year]).agg(
    n=("MonthStart", "size"), first=("MonthStart", "min"), af=("af", "first"), risk=("risk", "first"),
    GroupID=("GroupID", "first"), PlanID=("PlanID", "first"), Gender=("Gender", "first"), Age=("Age", "first"))
mem_years = mem_years[mem_years["n"] >= 3].reset_index()
p_cat = 0.0042 * mem_years["af"] * mem_years["risk"] * mem_years["n"] / 12
hit = mem_years[rng.random(len(mem_years)) < p_cat]
cat_rows = []
for r in hit.itertuples():
    diag = rng.choice(["Oncology", "Cardiovascular", "Neurology", "Other", "Maternity"],
                      p=[0.42, 0.25, 0.1, 0.13, 0.10])
    if diag == "Maternity" and not (r.Gender == "F" and 18 <= r.Age <= 44):
        diag = "Oncology"
    k = rng.integers(3, 9)
    start = r.first + pd.Timedelta(days=int(rng.integers(0, max(1, r.n * 30 - 60))))
    for j in range(k):
        d = start + pd.Timedelta(days=int(rng.integers(0, 150)))
        ctype = rng.choice(["Inpatient", "Outpatient", "Pharmacy"], p=[0.45, 0.35, 0.20])
        amt = float(np.exp(rng.normal(np.log({"Inpatient": 52000, "Outpatient": 14000, "Pharmacy": 9000}[ctype]), 0.6)))
        amt *= 1.08 ** ((d - pd.Timestamp("2024-01-01")).days / 365.25)
        cat_rows.append(dict(MemberID=r.MemberID, GroupID=r.GroupID, PlanID=r.PlanID, Gender=r.Gender, Age=r.Age,
                             MonthStart=d.to_period("M").to_timestamp(), risk=r.risk, ClaimType=ctype,
                             Allowed=amt, diag_fixed=diag, svc_fixed=d))
cat = pd.DataFrame(cat_rows)
# keep catastrophic claims within the member's enrollment and the data window
cat = cat.merge(members[["MemberID", "EnrollStart", "EnrollEnd"]], on="MemberID")
cat = cat[(cat["svc_fixed"] >= cat["EnrollStart"]) &
          (cat["svc_fixed"] <= cat["EnrollEnd"].fillna(pd.Timestamp("2026-08-31"))) &
          (cat["svc_fixed"] <= pd.Timestamp("2026-08-31"))].drop(columns=["EnrollStart", "EnrollEnd"])
claims = pd.concat([claims, cat], ignore_index=True)
N = len(claims)

# service date within month (catastrophic already have dates)
dim = claims["MonthStart"].dt.days_in_month.values
svc = claims["MonthStart"] + pd.to_timedelta(rng.integers(0, 31, N) % dim, unit="D")
claims["ServiceDate"] = np.where(claims["svc_fixed"].notna(), claims["svc_fixed"], svc) if "svc_fixed" in claims else svc
claims["ServiceDate"] = pd.to_datetime(claims["ServiceDate"])

# diagnosis category
diag = np.empty(N, dtype=object)
for ctype, dist in DIAG.items():
    sel = np.where((claims["ClaimType"] == ctype).values)[0]
    cats = list(dist); w = np.array(list(dist.values()), float); w /= w.sum()
    diag[sel] = rng.choice(cats, size=len(sel), p=w)
# maternity only for females 18-44; children get pediatric-ish mix
elig = (claims["Gender"].values == "F") & (claims["Age"].values >= 18) & (claims["Age"].values <= 44)
bad = (diag == "Maternity") & ~elig
diag[bad] = rng.choice(["Respiratory", "Injury", "Other", "Gastrointestinal"], size=bad.sum())
if "diag_fixed" in claims:
    fx = claims["diag_fixed"].notna().values
    diag[fx] = claims.loc[fx, "diag_fixed"].values
claims["DiagnosisCategory"] = diag
mult = claims["DiagnosisCategory"].map(DIAG_COST).fillna(1.0).values
mult = np.where(claims["diag_fixed"].notna().values, 1.0, mult) if "diag_fixed" in claims else mult
claims["Allowed"] = claims["Allowed"].values * mult
# maternity inpatient a bit cheaper, child claims cheaper
claims.loc[(claims["DiagnosisCategory"] == "Maternity") & (claims["ClaimType"] == "Inpatient"), "Allowed"] *= 0.62

# provider assignment
spec_for_diag = {
    "Preventive & Wellness": {"Family Medicine": 5, "Internal Medicine": 3, "Pediatrics": 3, "OB/GYN": 1},
    "Musculoskeletal": {"Orthopedics": 5, "Physical Therapy": 4, "Family Medicine": 1},
    "Behavioral Health": {"Behavioral Health": 9, "Family Medicine": 1},
    "Respiratory": {"Family Medicine": 4, "Pulmonology": 2, "Pediatrics": 2, "Internal Medicine": 2},
    "Cardiovascular": {"Cardiology": 6, "Internal Medicine": 3},
    "Diabetes & Endocrine": {"Endocrinology": 4, "Internal Medicine": 4, "Family Medicine": 2},
    "Gastrointestinal": {"Gastroenterology": 6, "Family Medicine": 2},
    "Maternity": {"OB/GYN": 1},
    "Neurology": {"Neurology": 6, "Family Medicine": 1},
    "Oncology": {"Oncology": 1},
    "Injury": {"Orthopedics": 3, "Family Medicine": 2},
    "Other": {"Dermatology": 4, "Family Medicine": 3, "Internal Medicine": 2},
}
pv = providers
by_spec = {s: pv[pv["Specialty"] == s] for s in pv["Specialty"].unique()}


def pick(df, n, popular=True):
    # skewed popularity so some providers carry much more volume
    w = np.arange(1, len(df) + 1, dtype=float) ** -0.8
    w = rng.permutation(w) if not popular else w
    return df["ProviderID"].values[rng.choice(len(df), size=n, p=w / w.sum())]


prov_col = np.empty(N, dtype=object)
ct = claims["ClaimType"].values
for t in ["Inpatient", "Emergency"]:
    s = np.where(ct == t)[0]
    prov_col[s] = pick(pv[pv["ProviderType"] == "Hospital"], len(s))
s = np.where(ct == "Pharmacy")[0]
ph = pv[pv["ProviderType"] == "Pharmacy"]
retail = ph[ph["Specialty"] == "Retail Pharmacy"]
choice = rng.random(len(s))
amt = claims["Allowed"].values[s]
prov_col[s] = np.where(amt > 2500, ph[ph["Specialty"] == "Specialty Pharmacy"]["ProviderID"].iloc[0],
                       np.where(choice < 0.22, ph[ph["Specialty"] == "Mail-Order Pharmacy"]["ProviderID"].iloc[0],
                                pick(retail, len(s))))
s = np.where(ct == "Outpatient")[0]
r = rng.random(len(s))
hosp = pick(pv[pv["ProviderType"] == "Hospital"], len(s))
lab = pick(pv[pv["ProviderType"] == "Imaging & Lab"], len(s))
asc = pick(pv[pv["ProviderType"] == "Ambulatory Surgery Center"], len(s))
uc = pick(pv[pv["ProviderType"] == "Urgent Care"], len(s))
prov_col[s] = np.select([r < 0.42, r < 0.72, r < 0.87], [hosp, lab, asc], uc)
s = np.where(ct == "Professional")[0]
dg = claims["DiagnosisCategory"].values[s]
ages = claims["Age"].values[s]
for d, sd in spec_for_diag.items():
    sel = s[dg == d]
    if not len(sel):
        continue
    sp = list(sd); w = np.array(list(sd.values()), float); w /= w.sum()
    chosen = rng.choice(sp, size=len(sel), p=w)
    a = claims["Age"].values[sel]
    chosen = np.where((a < 18) & np.isin(chosen, ["Family Medicine", "Internal Medicine"]), "Pediatrics", chosen)
    chosen = np.where((a >= 18) & (chosen == "Pediatrics"), "Family Medicine", chosen)
    out = np.empty(len(sel), dtype=object)
    for spn in np.unique(chosen):
        m = chosen == spn
        out[m] = pick(by_spec[spn], m.sum())
    prov_col[sel] = out
claims["ProviderID"] = prov_col
net = claims["ProviderID"].map(pv.set_index("ProviderID")["NetworkStatus"]).values
oon = net == "Out-of-Network"
claims.loc[oon, "Allowed"] *= 1.35  # OON allowed runs higher

# billed amount / network discount
disc = np.where(oon, rng.uniform(0.05, 0.18, N),
                np.select([ct == "Pharmacy", ct == "Inpatient", ct == "Outpatient", ct == "Emergency"],
                          [rng.uniform(0.15, 0.30, N), rng.uniform(0.45, 0.62, N), rng.uniform(0.40, 0.58, N),
                           rng.uniform(0.35, 0.50, N)], rng.uniform(0.30, 0.48, N)))
claims["Allowed"] = claims["Allowed"].round(2).clip(lower=4)
claims["Billed"] = (claims["Allowed"] / (1 - disc)).round(2)

# adjudication status, denials
deny_p = np.select([ct == "Pharmacy", ct == "Inpatient"], [0.035, 0.055], 0.075) * np.where(oon, 2.2, 1.0)
denied = rng.random(N) < deny_p
reasons_in = {"Prior authorization required": 24, "Duplicate claim": 18, "Not medically necessary": 16,
              "Coding error / missing information": 15, "Eligibility / coverage terminated": 9,
              "Non-covered service": 6, "Timely filing limit": 4, "No referral on file": 8}
reasons_oon = {"Out-of-network, no OON benefit": 35, "Prior authorization required": 20, "Duplicate claim": 12,
               "Not medically necessary": 10, "Coding error / missing information": 13, "No referral on file": 10}
dr = np.full(N, "", dtype=object)
for mask, dist in [(denied & ~oon, reasons_in), (denied & oon, reasons_oon)]:
    k = list(dist); w = np.array(list(dist.values()), float); w /= w.sum()
    dr[mask] = rng.choice(k, size=mask.sum(), p=w)
# EPO/HMO plans have no OON benefit; other plans less often
claims["DenialReason"] = dr

lag_mean = {"Pharmacy": 1.5, "Professional": 15, "Outpatient": 20, "Emergency": 22, "Inpatient": 31}
lag = np.array([rng.gamma(2.2, lag_mean[t] / 2.2) for t in ct]).round().astype(int) + np.where(ct == "Pharmacy", 0, 3)
lag = np.where(denied, (lag * 0.7).astype(int) + 2, lag)
claims["PaidDate"] = claims["ServiceDate"] + pd.to_timedelta(lag, unit="D")
pending = claims["PaidDate"] > AS_OF
claims["ClaimStatus"] = np.where(pending, "Pending", np.where(denied, "Denied", "Paid"))
claims.loc[pending, "DenialReason"] = ""

# member cost share with deductible / OOP accumulators (paid claims only)
claims = claims.sort_values(["MemberID", "ServiceDate"]).reset_index(drop=True)
ct = claims["ClaimType"].values
pl = claims["PlanID"].map(pi["PlanType"]).values
ded = claims["PlanID"].map(pi["Deductible"]).values.astype(float)
oop = claims["PlanID"].map(pi["OOPMax"]).values.astype(float)
coin = claims["PlanID"].map(pi["Coinsurance"]).values
paid_mask = (claims["ClaimStatus"] == "Paid").values
allowed = np.where(paid_mask, claims["Allowed"].values, 0.0)
copay = np.select(
    [ct == "Pharmacy", ct == "Professional", ct == "Emergency", ct == "Inpatient", ct == "Outpatient"],
    [rng.choice([10, 35, 60], len(claims), p=[0.62, 0.28, 0.10]),
     np.where(claims["DiagnosisCategory"].values == "Preventive & Wellness", 0, rng.choice([25, 45], len(claims))),
     250, 400, 100], 0).astype(float)
yr = claims["ServiceDate"].dt.year.values
key = claims["MemberID"].astype(str) + "_" + yr.astype(str)
# deductible applies to non-Rx services (HDHP: everything except preventive)
ded_applies = np.where(pl == "HDHP", claims["DiagnosisCategory"].values != "Preventive & Wellness",
                       (pl != "HMO") & np.isin(ct, ["Outpatient", "Inpatient", "Emergency"]))
ded_base = np.where(ded_applies, allowed, 0.0)
cum_before = pd.Series(ded_base).groupby(key.values).cumsum().values - ded_base
ded_part = np.clip(np.minimum(ded_base, ded - cum_before), 0, None)
remaining = allowed - ded_part
use_copay = (pl != "HDHP") & ~ded_applies
cs = np.where(use_copay, np.minimum(copay, remaining), remaining * coin) + ded_part
cs = np.minimum(cs, allowed)
cum_cs_before = pd.Series(cs).groupby(key.values).cumsum().values - cs
cs = np.clip(np.minimum(cs, oop - cum_cs_before), 0, None)
claims["MemberCostShare"] = cs.round(2)
claims["Paid"] = (allowed - cs).round(2)
claims.loc[~paid_mask, ["Paid", "MemberCostShare"]] = 0.0
claims["AllowedOut"] = np.where(paid_mask, claims["Allowed"], 0.0).round(2)
claims.loc[pending, "PaidDate"] = pd.NaT

claims = claims.sort_values(["ServiceDate", "MemberID"]).reset_index(drop=True)
claims["ClaimID"] = [f"CLM{26000000 + i:08d}" for i in range(len(claims))]
claims_out = pd.DataFrame({
    "ClaimID": claims["ClaimID"], "MemberID": claims["MemberID"], "GroupID": claims["GroupID"],
    "PlanID": claims["PlanID"], "ProviderID": claims["ProviderID"],
    "ServiceDate": claims["ServiceDate"].dt.strftime("%Y-%m-%d"),
    "PaidDate": claims["PaidDate"].dt.strftime("%Y-%m-%d").fillna(""),
    "ClaimType": claims["ClaimType"], "DiagnosisCategory": claims["DiagnosisCategory"],
    "ClaimStatus": claims["ClaimStatus"], "DenialReason": claims["DenialReason"],
    "BilledAmount": claims["Billed"], "AllowedAmount": claims["AllowedOut"],
    "MemberCostShare": claims["MemberCostShare"], "PaidAmount": claims["Paid"],
})

# ---------------------------------------------------------------- calibrate premium to a 2024 loss ratio of ~85.5%
paid24 = claims_out.loc[claims_out["ServiceDate"] < "2025-01-01", "PaidAmount"].sum()
prem24 = enrollment.loc[enrollment["MonthStart"] < "2025-01-01", "PremiumAmount"].sum()
k = paid24 / prem24 / 0.855
enrollment["PremiumAmount"] = (enrollment["PremiumAmount"] * k).round(2)
print("premium scale", round(k, 4))

# ---------------------------------------------------------------- write
groups_out = groups[["GroupID", "GroupName", "Industry", "State", "MarketSegment", "RenewalMonth",
                     "EffectiveDate", "TermDate", "GroupStatus"]].copy()
groups_out["EffectiveDate"] = groups_out["EffectiveDate"].dt.strftime("%Y-%m-%d")
groups_out["TermDate"] = groups_out["TermDate"].dt.strftime("%Y-%m-%d").fillna("")
plans_out = plans[["PlanID", "PlanName", "PlanType", "Deductible", "OOPMax", "Coinsurance"]]
members_out = members[["MemberID", "GroupID", "PlanID", "Relationship", "Gender", "BirthDate", "Age", "AgeBand",
                       "EnrollStart", "EnrollEnd"]].copy()
for c in ["BirthDate", "EnrollStart", "EnrollEnd"]:
    members_out[c] = members_out[c].dt.strftime("%Y-%m-%d").fillna("")
enroll_out = enrollment.copy()
enroll_out["MonthStart"] = enroll_out["MonthStart"].dt.strftime("%Y-%m-%d")

import os
os.makedirs(OUT, exist_ok=True)
claims_out.to_csv(f"{OUT}/claims.csv", index=False)
members_out.to_csv(f"{OUT}/members.csv", index=False)
groups_out.to_csv(f"{OUT}/groups.csv", index=False)
plans_out.to_csv(f"{OUT}/plans.csv", index=False)
providers.to_csv(f"{OUT}/providers.csv", index=False)
enroll_out.to_csv(f"{OUT}/enrollment.csv", index=False)
for n_, d_ in [("claims", claims_out), ("members", members_out), ("groups", groups_out), ("plans", plans_out),
               ("providers", providers), ("enrollment", enroll_out)]:
    print(n_, d_.shape)
