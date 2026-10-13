"""Calibrated synthetic order generator for the Zomato dbt project.

Regenerates ORDERS, ORDER_ITEMS and REVIEWS on top of the real dimension files
(Swiggy-scraped restaurants + menus, the 100K-user panel), with realistic customer
lifecycle behaviour: staggered acquisition, early-tenure churn, resurrection,
seasonality, price drift and city-level operations. All knobs live in params.yml.

Usage (from the repo root):
    .venv/bin/python -I data_generator/generate.py --calibrate   # lifecycle + volume check only
    .venv/bin/python -I data_generator/generate.py               # full run, writes data_generator/output/
"""

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

HERE = Path(__file__).resolve().parent
RAW_DIR = HERE.parent / "zomato_engineering_raw_data"
OUT_DIR = HERE / "output"


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# --------------------------------------------------------------------------------------
# Calendar
# --------------------------------------------------------------------------------------
class Calendar:
    def __init__(self, cfg):
        self.history_start = np.datetime64(cfg["history_start"])
        self.report_start = np.datetime64(cfg["report_start"])
        self.end = np.datetime64(cfg["end"])
        self.months = np.arange(
            self.history_start.astype("datetime64[M]"),
            self.end.astype("datetime64[M]") + 1,
        )
        self.n_months = len(self.months)
        self.month_start_day = self.months.astype("datetime64[D]")
        nxt = (self.months + 1).astype("datetime64[D]")
        self.days_in_month = (nxt - self.month_start_day).astype(int)
        self.cal_month = (self.months.astype(int) % 12) + 1
        self.report_month_idx = int(
            np.searchsorted(self.months, self.report_start.astype("datetime64[M]"))
        )


# --------------------------------------------------------------------------------------
# Dimension loading
# --------------------------------------------------------------------------------------
def load_dimensions(p):
    log("loading dimension files")
    rest = pd.read_csv(
        RAW_DIR / "restaurant.csv",
        usecols=["id", "city", "rating_count", "cuisine"],
        dtype={"city": str, "rating_count": str, "cuisine": str},
    )
    rest["metro"] = rest["city"].str.split(",").str[-1].str.strip()
    pop = p["restaurants"]["popularity_by_rating_count"]
    rest["pop_w"] = rest["rating_count"].map(pop).fillna(1.0).astype(float)
    rest["primary_tag"] = rest["cuisine"].fillna("").str.split(",").str[0].str.strip()

    menu = pd.read_csv(
        RAW_DIR / "menu.csv", usecols=["r_id", "f_id", "price"], dtype={"price": str, "f_id": str}
    )
    menu["price"] = pd.to_numeric(menu["price"], errors="coerce")
    b = p["basket"]
    menu = menu[(menu["price"] >= b["menu_price_min"]) & (menu["price"] <= b["menu_price_max"])]
    menu = menu.drop_duplicates(["r_id", "f_id"]).sort_values(["r_id", "f_id"]).reset_index(drop=True)

    users = pd.read_csv(RAW_DIR / "users.csv", usecols=["user_id", "Occupation"])
    reviews = pd.read_csv(RAW_DIR / "reviews.csv", usecols=["rating", "comment"])
    log(f"  restaurants={len(rest):,} menu_rows={len(menu):,} users={len(users):,}")
    return rest, menu, users, reviews


def build_menus(rest, menu, rng):
    """Each restaurant gets a menu: its own if it has one, otherwise a donor restaurant's menu
    with the same primary cuisine tag (only 12K of 148K listings have a scraped menu)."""
    by_r = menu.groupby("r_id", sort=True)
    menu_rids = np.array(list(by_r.groups.keys()))
    starts = by_r.indices
    menu_start_by_rid = {rid: idx[0] for rid, idx in starts.items()}
    menu_len_by_rid = {rid: len(idx) for rid, idx in starts.items()}

    has_menu = rest["id"].isin(menu_rids).to_numpy()
    donor_tag = rest.loc[has_menu, ["id", "primary_tag"]]
    pools = {tag: grp["id"].to_numpy() for tag, grp in donor_tag.groupby("primary_tag")}
    all_donors = donor_tag["id"].to_numpy()

    donor = rest["id"].to_numpy().copy()
    tags = rest["primary_tag"].to_numpy()
    no_menu_idx = np.where(~has_menu)[0]
    for tag, idxs in pd.Series(no_menu_idx).groupby(tags[no_menu_idx]):
        pool = pools.get(tag, all_donors)
        donor[idxs.to_numpy()] = rng.choice(pool, size=len(idxs))

    rest["menu_start"] = [menu_start_by_rid[d] for d in donor]
    rest["menu_len"] = [menu_len_by_rid[d] for d in donor]
    rest["has_own_menu"] = has_menu
    log(f"  restaurants with own menu: {has_menu.sum():,}; others use a same-cuisine donor menu")
    return rest


# --------------------------------------------------------------------------------------
# Order-level attribute helpers (shared by first orders and repeat orders)
# --------------------------------------------------------------------------------------
class Ops:
    def __init__(self, p, rest, rng):
        o = p["operations"]
        self.o = o
        metros = rest["metro"].unique()
        lo, hi = o["delivery_base_minutes_range"]
        self.metro_index = {m: i for i, m in enumerate(metros)}
        self.delivery_base = rng.uniform(lo, hi, size=len(metros))
        self.cancel_mult = rng.lognormal(0.0, o["cancel_city_sd"], size=len(metros))
        self.rest_metro_idx = rest["metro"].map(self.metro_index).to_numpy()

    def delivery_minutes(self, rest_idx, hour, cal_month, is_weekend, rng):
        o = self.o
        base = self.delivery_base[self.rest_metro_idx[rest_idx]]
        peak = np.isin(hour, [12, 13, 19, 20, 21]) * o["peak_hour_extra_minutes"]
        monsoon = np.isin(cal_month, [7, 8, 9]) * o["monsoon_extra_minutes"]
        wknd = is_weekend * o["weekend_extra_minutes"]
        mins = base + peak + monsoon + wknd + rng.normal(0, o["delivery_noise_sd"], size=len(rest_idx))
        return np.clip(np.round(mins), o["delivery_min"], o["delivery_max"]).astype(np.int32)

    def rating(self, minutes, rng):
        o = self.o
        raw = o["rating_intercept"] - o["rating_slope_per_minute"] * (minutes - 30) + rng.normal(
            0, o["rating_noise_sd"], size=len(minutes)
        )
        r = np.clip(np.round(raw), 1, 5).astype(np.float64)
        r[rng.random(len(minutes)) >= o["rated_share_of_delivered"]] = np.nan
        return r

    def status(self, rest_idx, hour, cal_month, rng):
        o = self.o
        p_cancel = (
            o["cancel_rate_base"]
            * self.cancel_mult[self.rest_metro_idx[rest_idx]]
            * np.where(np.isin(cal_month, [7, 8, 9]), o["monsoon_cancel_multiplier"], 1.0)
            * np.where(np.isin(hour, [12, 13, 19, 20, 21]), 1.1, 1.0)
        )
        u = rng.random(len(rest_idx))
        out = np.full(len(rest_idx), "Delivered", dtype=object)
        out[u < p_cancel] = "Cancelled"
        out[(u >= p_cancel) & (u < p_cancel + o["refund_rate"])] = "Refunded"
        return out


def sample_restaurants_in_metro(metro_codes, rest, rng):
    """Popularity-weighted restaurant draw within each order's metro."""
    out = np.empty(len(metro_codes), dtype=np.int64)
    rest_metro = rest["metro_code"].to_numpy()
    w = rest["pop_w"].to_numpy()
    order = np.argsort(rest_metro, kind="stable")
    bounds = np.searchsorted(rest_metro[order], np.arange(rest_metro.max() + 2))
    by_metro = np.argsort(metro_codes, kind="stable")
    uniq, first_pos = np.unique(metro_codes[by_metro], return_index=True)
    ends = np.append(first_pos[1:], len(by_metro))
    for m, a, b in zip(uniq, first_pos, ends):
        sel = by_metro[a:b]
        cand = order[bounds[m] : bounds[m + 1]]
        cw = np.cumsum(w[cand])
        out[sel] = cand[np.searchsorted(cw, rng.random(len(sel)) * cw[-1], side="right")]
    return out


# --------------------------------------------------------------------------------------
# Customers + lifecycle simulation
# --------------------------------------------------------------------------------------
def build_customers(p, cal, rest, users, rng):
    n = len(users)
    a = p["acquisition"]
    lc = p["lifecycle"]

    # Home metro weighted by restaurant popularity mass (big cities dominate).
    metro_w = rest.groupby("metro_code")["pop_w"].sum()
    home = rng.choice(metro_w.index.to_numpy(), size=n, p=(metro_w / metro_w.sum()).to_numpy())

    # Acquisition month: existing base spread over the burn-in, the rest arriving with growth.
    burn = cal.report_month_idx
    n_existing = int(round(n * a["existing_base_share"]))
    later = np.arange(burn, cal.n_months)
    w = (1 + a["new_arrival_yoy_growth"]) ** ((later - burn) / 12.0)
    w = w * np.where(np.isin(cal.cal_month[later], [10, 11, 12]), a["festive_arrival_uplift"], 1.0)
    # Existing customers mostly show up early in the burn-in (they're already active).
    bw = np.array(a["existing_first_order_month_weights"][:burn], dtype=float)
    acq = np.concatenate([
        rng.choice(burn, size=n_existing, p=bw / bw.sum()),
        rng.choice(later, size=n - n_existing, p=w / w.sum()),
    ])
    lo, hi = a["existing_base_tenure_months"]
    offset = np.concatenate([rng.integers(lo, hi + 1, size=n_existing), np.zeros(n - n_existing, dtype=int)])
    perm = rng.permutation(n)
    acq, offset = acq[perm], offset[perm]
    acq_day = (rng.random(n) * cal.days_in_month[acq]).astype(int)  # 0-based day in month

    occ_mult = users["Occupation"].map(lc["occupation_rate_multiplier"]).fillna(1.0).to_numpy()
    shape = lc["order_rate_gamma_shape"]
    lam = rng.gamma(shape, 1.0 / shape, size=n) * occ_mult

    return pd.DataFrame({
        "user_id": users["user_id"].to_numpy(),
        "home_metro": home,
        "acq_month": acq,
        "acq_day": acq_day,
        "lam": lam,
        "tenure_offset": offset,   # >0 = existing customer with prior (unobserved) tenure
    })


def simulate_lifecycle(p, cal, cust, first, scale, seed):
    """Returns (counts[n, months], comeback_month_flag[n, months]). counts includes the first order."""
    rng = np.random.default_rng(seed)
    lc = p["lifecycle"]
    pe = p["planted_effects"]
    n = len(cust)
    M = cal.n_months
    season = np.array([p["seasonality"][m] for m in cal.cal_month])
    years = np.arange(M) / 12.0
    trend = (1 + lc["frequency_trend_per_year"]) ** years
    festive = np.isin(cal.cal_month, [10, 11, 12])

    acq = cust["acq_month"].to_numpy()
    lam = cust["lam"].to_numpy() * scale
    slow = first["slow"].to_numpy()
    poor = first["poor"].to_numpy()
    disc = first["discounted"].to_numpy()

    offset = cust["tenure_offset"].to_numpy()
    is_new = offset == 0
    lapse_mult = np.where(disc & is_new, pe["discount_acquired_lapse_multiplier"], 1.0)
    early_mult = np.where(slow, pe["slow_first_lapse_multiplier"], 1.0) * np.where(
        poor, pe["poor_first_lapse_multiplier"], 1.0
    )
    early_mult = np.where(is_new, early_mult, 1.0)
    early_rate = np.where(slow & is_new, pe["slow_first_early_order_multiplier"], 1.0)

    counts = np.zeros((n, M), dtype=np.int32)
    comeback = np.zeros((n, M), dtype=bool)
    engaged = np.zeros(n, dtype=bool)

    for m in range(M):
        at_acq = acq == m
        after = acq < m
        tenure = m - acq
        eff_tenure = tenure + offset   # existing customers sit further down the hazard curve

        # Acquisition month: the first order + extra orders on the remaining (later) days.
        remaining = (cal.days_in_month[m] - 1 - cust["acq_day"].to_numpy()) / cal.days_in_month[m]
        extra = rng.poisson(lam * season[m] * trend[m] * np.clip(remaining, 0, 1) * early_rate)
        counts[at_acq, m] = 1 + extra[at_acq]
        engaged[at_acq] = True

        # Engaged customers may lapse; lapsed ones may come back.
        h = lc["lapse_hazard_floor"] + (lc["lapse_hazard_first"] - lc["lapse_hazard_floor"]) * np.exp(
            -(np.maximum(eff_tenure, 1) - 1) / lc["lapse_hazard_decay_months"]
        )
        h = h * lapse_mult * np.where(tenure == 1, early_mult, 1.0)
        u = rng.random(n)
        lapse_now = after & engaged & (u < np.clip(h, 0, 0.95))
        r = lc["resurrection_prob"] * (lc["festive_resurrection_uplift"] if festive[m] else 1.0)
        back_now = after & ~engaged & (u < r)
        engaged[lapse_now] = False
        engaged[back_now] = True

        active_rate = lam * season[m] * trend[m] * np.where(tenure == 1, early_rate, 1.0)
        n_orders = rng.poisson(active_rate)
        n_orders[back_now] = np.maximum(n_orders[back_now], 1)
        sel = after & engaged
        counts[sel, m] = n_orders[sel]
        comeback[back_now, m] = True

    # Extras can't fit when acquisition is on the month's last day.
    last_day = cust["acq_day"].to_numpy() == cal.days_in_month[acq] - 1
    counts[np.where(last_day)[0], acq[last_day]] = 1
    return counts, comeback


def lifecycle_report(cal, counts):
    active = counts > 0
    mau = active.sum(axis=0)
    orders = counts.sum(axis=0)
    rep = pd.DataFrame({"month": cal.months.astype(str), "mau": mau, "orders": orders})
    rep["orders_per_active"] = (rep.orders / rep.mau.clip(lower=1)).round(2)
    rep["mau_yoy"] = (rep.mau / rep.mau.shift(12) - 1).round(3)
    return rep


# --------------------------------------------------------------------------------------
# Main generation
# --------------------------------------------------------------------------------------
def first_order_attributes(p, cal, cust, rest, ops, rng):
    n = len(cust)
    hour = rng.choice(24, size=n, p=np.array(p["hour_weights"]) / sum(p["hour_weights"]))
    date = cal.month_start_day[cust.acq_month.to_numpy()] + cust.acq_day.to_numpy().astype("timedelta64[D]")
    cal_month = cal.cal_month[cust.acq_month.to_numpy()]
    wknd = pd.DatetimeIndex(date).dayofweek.to_numpy() >= 5
    r_idx = sample_restaurants_in_metro(cust.home_metro.to_numpy(), rest, rng)
    minutes = ops.delivery_minutes(r_idx, hour, cal_month, wknd, rng)
    rating = ops.rating(minutes, rng)
    discounted = rng.random(n) < p["pricing"]["discount_prob_first_order"]
    pe = p["planted_effects"]
    return pd.DataFrame({
        "date": date, "hour": hour, "rest_idx": r_idx, "minutes": minutes, "rating": rating,
        "discounted": discounted,
        "slow": minutes > pe["slow_first_delivery_minutes"],
        "poor": rating < pe["poor_first_rating_threshold"],  # NaN compares False: unrated isn't 'poor'
    })


def calibrate_scale(p, cal, cust, first, seed):
    target = p["volume"]["target_orders_in_report_window"]
    scale = 7.0
    for i in range(4):
        counts, _ = simulate_lifecycle(p, cal, cust, first, scale, seed)
        got = counts[:, cal.report_month_idx :].sum()
        log(f"  calibration pass {i + 1}: scale={scale:.3f} -> {got:,} orders in report window")
        if abs(got / target - 1) < 0.005:
            break
        scale *= target / got
    return scale


def expand_orders(p, cal, cust, first, counts, comeback, rest, ops, rng):
    log("expanding customer-months into orders")
    ci, mi = np.nonzero(counts)
    k = counts[ci, mi]
    o_cust = np.repeat(ci, k)
    o_month = np.repeat(mi, k)
    o_rank = np.arange(len(o_cust)) - np.repeat(np.cumsum(k) - k, k)  # 0-based index within customer-month
    acq = cust.acq_month.to_numpy()
    is_first = (o_month == acq[o_cust]) & (o_rank == 0)
    is_comeback = comeback[o_cust, o_month] & (o_rank == 0)
    n = len(o_cust)
    log(f"  {n:,} orders")

    # Day of month
    dim = cal.days_in_month[o_month]
    day = np.empty(n, dtype=np.int64)
    acq_m = o_month == acq[o_cust]
    acq_day = cust.acq_day.to_numpy()[o_cust]
    # acquisition month: first order on acq_day, extras strictly after it
    day[is_first] = acq_day[is_first]
    ex = acq_m & ~is_first
    day[ex] = acq_day[ex] + 1 + (rng.random(ex.sum()) * (dim[ex] - 1 - acq_day[ex])).astype(int)
    # other months: weekend-weighted day draw
    other = ~acq_m
    wkend_w = p["weekend_uplift"]
    for m in np.unique(o_month[other]):
        sel = np.where(other & (o_month == m))[0]
        days = cal.month_start_day[m] + np.arange(cal.days_in_month[m]).astype("timedelta64[D]")
        w = np.where(pd.DatetimeIndex(days).dayofweek >= 5, wkend_w, 1.0)
        cw = np.cumsum(w)
        day[sel] = np.searchsorted(cw, rng.random(len(sel)) * cw[-1], side="right")

    date = cal.month_start_day[o_month] + day.astype("timedelta64[D]")
    hw = np.array(p["hour_weights"]) / sum(p["hour_weights"])
    hour = rng.choice(24, size=n, p=hw)
    hour[is_first] = first.hour.to_numpy()[o_cust[is_first]]
    secs = rng.integers(0, 3600, size=n)
    ts = date.astype("datetime64[s]") + (hour * 3600 + secs).astype("timedelta64[s]")
    cal_month = cal.cal_month[o_month]
    wknd = pd.DatetimeIndex(date).dayofweek.to_numpy() >= 5

    # Restaurant choice: favourites / home-metro popularity / occasional out-of-town
    log("  choosing restaurants")
    rc = p["restaurants"]
    n_fav = rc["favourites_per_customer"]
    favs = sample_restaurants_in_metro(np.repeat(cust.home_metro.to_numpy(), n_fav), rest, rng).reshape(-1, n_fav)
    home = cust.home_metro.to_numpy()[o_cust]
    u = rng.random(n)
    travel = u < rc["out_of_home_city_share"]
    metro_mass = rest.groupby("metro_code")["pop_w"].sum()
    metro_draw = home.copy()
    metro_draw[travel] = rng.choice(
        metro_mass.index.to_numpy(), size=travel.sum(), p=(metro_mass / metro_mass.sum()).to_numpy()
    )
    r_idx = sample_restaurants_in_metro(metro_draw, rest, rng)
    use_fav = ~travel & (rng.random(n) < rc["favourite_order_share"])
    r_idx[use_fav] = favs[o_cust[use_fav], rng.integers(0, n_fav, size=use_fav.sum())]
    r_idx[is_first] = first.rest_idx.to_numpy()[o_cust[is_first]]

    # Status, delivery time, rating
    log("  operations: status, delivery time, rating")
    status = ops.status(r_idx, hour, cal_month, rng)
    status[is_first] = "Delivered"
    delivered = status == "Delivered"
    minutes = ops.delivery_minutes(r_idx, hour, cal_month, wknd, rng).astype(np.float64)
    minutes[is_first] = first.minutes.to_numpy()[o_cust[is_first]]
    rating = ops.rating(minutes, rng)
    rating[is_first] = first.rating.to_numpy()[o_cust[is_first]]
    minutes[~delivered] = np.nan
    rating[~delivered] = np.nan

    # Discount flag
    pr = p["pricing"]
    disc_p = np.where(is_comeback, pr["discount_prob_comeback_order"], pr["discount_prob_other"])
    discounted = rng.random(n) < disc_p
    discounted[is_first] = first.discounted.to_numpy()[o_cust[is_first]]

    orders = pd.DataFrame({
        "cust": o_cust, "ts": ts, "date": date, "rest_idx": r_idx, "status": status,
        "minutes": minutes, "rating": rating, "discounted": discounted,
        "is_first": is_first, "is_comeback": is_comeback,
    })
    orders.sort_values(["ts", "cust"], inplace=True, kind="stable")
    orders.reset_index(drop=True, inplace=True)
    orders["order_id"] = np.arange(1, len(orders) + 1, dtype=np.int64)
    return orders


def build_items_and_amounts(p, cal, orders, rest, menu, rng):
    log("building order items")
    b = p["basket"]
    n = len(orders)
    r_idx = orders.rest_idx.to_numpy()
    mstart = rest.menu_start.to_numpy()[r_idx]
    mlen = rest.menu_len.to_numpy()[r_idx]

    ic_vals = np.array(list(b["items_count_probs"].keys()))
    ic_p = np.array(list(b["items_count_probs"].values()), dtype=float)
    k = np.minimum(rng.choice(ic_vals, size=n, p=ic_p / ic_p.sum()), mlen)

    oi = np.repeat(np.arange(n), k)
    pos = (rng.random(len(oi)) * np.repeat(mlen, k)).astype(np.int64)
    fidx = np.repeat(mstart, k) + pos
    # drop duplicate food items within an order
    key = oi.astype(np.int64) * (len(menu) + 1) + fidx
    _, keep = np.unique(key, return_index=True)
    keep.sort()
    oi, fidx = oi[keep], fidx[keep]

    q_vals = np.array(list(b["quantity_probs"].keys()))
    q_p = np.array(list(b["quantity_probs"].values()), dtype=float)
    qty = rng.choice(q_vals, size=len(oi), p=q_p / q_p.sum())

    years = (orders.date.to_numpy() - cal.history_start).astype("timedelta64[D]").astype(int) / 365.25
    infl = (1 + b["price_inflation_per_year"]) ** years
    base = menu.price.to_numpy()[fidx]
    price = np.maximum(1, np.round(base * infl[oi])).astype(np.int64)
    line = price * qty

    subtotal = np.bincount(oi, weights=line, minlength=n).astype(np.int64)
    items_count = np.bincount(oi, minlength=n).astype(np.int64)
    sales_qty = np.bincount(oi, weights=qty, minlength=n).astype(np.int64)

    pr = p["pricing"]
    lo, hi = pr["discount_pct_range"]
    pct = rng.uniform(lo, hi, size=n)
    discount = np.where(orders.discounted.to_numpy(), np.round(subtotal * pct), 0).astype(np.int64)
    fee = rng.choice(pr["delivery_fee_values"], size=n, p=np.array(pr["delivery_fee_probs"]) / sum(pr["delivery_fee_probs"]))
    gst = np.round(subtotal * pr["gst_rate"]).astype(np.int64)
    pay = rng.choice(pr["payment_methods"], size=n, p=np.array(pr["payment_probs"]) / sum(pr["payment_probs"]))

    orders["items_count"] = items_count
    orders["sales_qty"] = sales_qty
    orders["subtotal"] = subtotal
    orders["discount"] = discount
    orders["delivery_fee"] = fee
    orders["gst"] = gst
    orders["sales_amount"] = subtotal - discount + fee + gst
    orders["payment_method"] = pay

    items = pd.DataFrame({
        "order_item_id": np.arange(1, len(oi) + 1, dtype=np.int64),
        "order_id": orders.order_id.to_numpy()[oi],
        "r_id": rest.id.to_numpy()[r_idx[oi]],
        "f_id": menu.f_id.to_numpy()[fidx],
        "price": price,
        "quantity": qty,
        "line_amount": line,
    })
    log(f"  {len(items):,} order items")
    return items


def build_reviews(p, cal, orders, reviews_pool, rng):
    rv = p["reviews"]
    cand = orders[(orders.status == "Delivered") & orders.rating.notna()]
    w = np.where(cand.rating.isin([1, 2, 5]), rv["extreme_rating_review_multiplier"], 1.0)
    prob = rv["review_share_of_rated"] * w / w.mean()
    pick = cand[rng.random(len(cand)) < prob]
    lag = rng.integers(0, rv["max_lag_days"] + 1, size=len(pick)).astype("timedelta64[D]")
    rdate = np.minimum(pick.date.to_numpy() + lag, cal.end)
    pools = {r: g.comment.dropna().unique() for r, g in reviews_pool.groupby("rating")}
    ratings = pick.rating.astype(int).to_numpy()
    comments = np.empty(len(pick), dtype=object)
    for r in np.unique(ratings):
        sel = ratings == r
        comments[sel] = rng.choice(pools[r], size=sel.sum())
    out = pd.DataFrame({
        "review_id": np.arange(1, len(pick) + 1, dtype=np.int64),
        "order_id": pick.order_id.to_numpy(),
        "user_id": pick.user_id.to_numpy(),
        "restaurant_id": pick.r_id.to_numpy(),
        "rating": ratings,
        "comment": comments,
        "review_date": rdate,
    })
    log(f"  {len(out):,} reviews")
    return out


def ground_truth(orders):
    """Recompute what mart_retention_diagnostic should report, with the mart's exact rules:
    first/second *delivered* order per customer (ordered by date, order_id); unrated first
    orders get the mart's 'Unrated' bucket."""
    d = orders.loc[orders.status == "Delivered", ["user_id", "order_id", "date", "minutes", "rating", "discount"]]
    d = d.sort_values(["user_id", "date", "order_id"])
    d["seq"] = d.groupby("user_id").cumcount() + 1
    f = d[d.seq == 1].set_index("user_id")
    s = d[d.seq == 2].set_index("user_id")
    days = (s.date - f.date.reindex(s.index)).dt.days
    reorder30 = pd.Series(False, index=f.index)
    reorder30.loc[days[days <= 30].index] = True

    speed = np.select(
        [f.minutes <= 20, f.minutes <= 30, f.minutes <= 40],
        ["Very Fast (0-20 min)", "Fast (20-30 min)", "Moderate (30-40 min)"], "Slow (40+ min)")
    rate = np.select(
        [f.rating.isna(), f.rating >= 4.5, f.rating >= 4.0, f.rating >= 3.0],
        ["Unrated", "Excellent (4.5-5.0)", "Good (4.0-4.5)", "Fair (3.0-4.0)"], "Poor (<3.0)")
    disc = np.where(f.discount > 0, "true", "false")
    rows = []
    for dim, labels in [("delivery_speed_bucket", speed), ("rating_bucket", rate), ("did_use_discount_on_first_order", disc)]:
        g = pd.DataFrame({"bucket": labels, "r30": reorder30.reindex(f.index).to_numpy()}).groupby("bucket")
        for bucket, grp in g:
            rows.append({"dimension": dim, "bucket": bucket, "customers": len(grp), "reorders_within_30d": int(grp.r30.sum())})
    return pd.DataFrame(rows)


def write_csv(df, name, chunk_rows=2_000_000):
    d = OUT_DIR / name
    d.mkdir(parents=True, exist_ok=True)
    for f in d.glob("*.csv.gz"):
        f.unlink()
    for i, start in enumerate(range(0, len(df), chunk_rows)):
        df.iloc[start : start + chunk_rows].to_csv(
            d / f"{name}_{i:03d}.csv.gz", index=False, date_format="%Y-%m-%d %H:%M:%S",
            compression={"method": "gzip", "compresslevel": 1},
        )
    log(f"  wrote {name}: {len(df):,} rows")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--calibrate", action="store_true", help="lifecycle + volume report only")
    args = ap.parse_args()

    p = yaml.safe_load((HERE / "params.yml").read_text())
    rng = np.random.default_rng(p["seed"])
    cal = Calendar(p["calendar"])

    rest, menu, users, reviews_pool = load_dimensions(p)
    rest = build_menus(rest, menu, rng)
    rest["metro_code"] = rest["metro"].astype("category").cat.codes.astype(np.int64)
    ops = Ops(p, rest, rng)

    cust = build_customers(p, cal, rest, users, rng)
    first = first_order_attributes(p, cal, cust, rest, ops, rng)
    log(f"first orders: slow={first.slow.mean():.1%} poor={first.poor.mean():.1%} discounted={first.discounted.mean():.1%}")

    log("calibrating order rate to target volume")
    scale = calibrate_scale(p, cal, cust, first, p["seed"] + 1)
    counts, comeback = simulate_lifecycle(p, cal, cust, first, scale, p["seed"] + 1)
    rep = lifecycle_report(cal, counts)
    print(rep.to_string(index=False))
    if args.calibrate:
        return

    orders = expand_orders(p, cal, cust, first, counts, comeback, rest, ops, rng)
    orders["user_id"] = cust.user_id.to_numpy()[orders.cust.to_numpy()]
    orders["r_id"] = rest.id.to_numpy()[orders.rest_idx.to_numpy()]
    orders["restaurant_city"] = rest.city.to_numpy()[orders.rest_idx.to_numpy()]
    orders["cuisine"] = rest.cuisine.to_numpy()[orders.rest_idx.to_numpy()]
    items = build_items_and_amounts(p, cal, orders, rest, menu, rng)
    reviews = build_reviews(p, cal, orders, reviews_pool, rng)

    out = pd.DataFrame({
        "order_id": orders.order_id,
        "order_timestamp": orders.ts,
        "order_date": orders.date.dt.strftime("%Y-%m-%d"),
        "user_id": orders.user_id,
        "r_id": orders.r_id,
        "restaurant_city": orders.restaurant_city,
        "cuisine": orders.cuisine,
        "items_count": orders.items_count,
        "sales_qty": orders.sales_qty,
        "subtotal": orders.subtotal,
        "discount": orders.discount,
        "delivery_fee": orders.delivery_fee,
        "gst": orders.gst,
        "sales_amount": orders.sales_amount,
        "currency": "INR",
        "payment_method": orders.payment_method,
        "order_status": orders.status,
        "customer_rating": orders.rating.astype("Int64"),
        "delivery_time_min": orders.minutes.astype("Int64"),
    })

    log("writing output")
    OUT_DIR.mkdir(exist_ok=True)
    write_csv(out, "orders")
    write_csv(items, "order_items")
    reviews["review_date"] = pd.to_datetime(reviews.review_date).dt.strftime("%Y-%m-%d")
    write_csv(reviews, "reviews")

    gt = ground_truth(orders.assign(discount=out.discount))
    gt.to_csv(HERE.parent / "zomato" / "seeds" / "generator_ground_truth.csv", index=False)

    in_window = (orders.date >= cal.report_start).sum()
    summary = {
        "orders_total": int(len(orders)),
        "orders_in_report_window": int(in_window),
        "order_items": int(len(items)),
        "reviews": int(len(reviews)),
        "customers": int(orders.user_id.nunique()),
        "restaurants_used": int(orders.r_id.nunique()),
        "rate_scale": round(float(scale), 4),
        "cancel_rate": round(float((orders.status == "Cancelled").mean()), 4),
        "discounted_share": round(float(orders.discounted.mean()), 4),
        "aov_inr_delivered_by_year": {
            str(y): round(float(v), 1)
            for y, v in out[orders.status == "Delivered"].groupby(orders.date.dt.year).sales_amount.mean().items()
        },
        "rating_delivery_corr": round(float(orders[["rating", "minutes"]].corr().iloc[0, 1]), 3),
        "monthly": rep.to_dict(orient="records"),
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2))
    log("done: " + json.dumps({k: v for k, v in summary.items() if k != "monthly"}))


if __name__ == "__main__":
    main()
