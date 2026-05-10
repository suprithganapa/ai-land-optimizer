import pandas as pd
import numpy as np
import os

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
RAW_PATH  = os.path.join(BASE_DIR, "Bengaluru_House_Data.csv")
OUT_PATH  = os.path.join(BASE_DIR, "bengaluru_land_rates.csv")

print("📂 Loading Kaggle dataset...")
df = pd.read_csv(RAW_PATH)
print(f"   Raw rows: {len(df)}")

# ── Clean total_sqft ──────────────────────────────────────
def parse_sqft(val):
    try:
        val = str(val).strip()
        if '-' in val:
            parts = val.split('-')
            return (float(parts[0].strip()) + float(parts[1].strip())) / 2
        return float(val)
    except:
        return np.nan

df['sqft_clean']  = df['total_sqft'].apply(parse_sqft)
df['price_clean'] = pd.to_numeric(df['price'], errors='coerce')

# ── Drop bad rows ─────────────────────────────────────────
df = df.dropna(subset=['sqft_clean', 'price_clean', 'location'])
df = df[df['sqft_clean'] > 100]
df = df[df['price_clean'] > 1]
df['location'] = df['location'].str.strip()

# ── Calculate price per m² ────────────────────────────────
df['price_per_m2'] = (df['price_clean'] * 100000) / df['sqft_clean'] * 10.764

print(f"   After cleaning: {len(df)} rows")

# ── Remove outliers per location (keep location column) ───
def remove_outliers_group(group):
    q1 = group['price_per_m2'].quantile(0.15)
    q3 = group['price_per_m2'].quantile(0.85)
    return group[(group['price_per_m2'] >= q1) & (group['price_per_m2'] <= q3)]

df_clean = df.groupby('location', group_keys=False)[df.columns].apply(remove_outliers_group)
df_clean = df_clean.reset_index(drop=True)
print(f"   After outlier removal: {len(df_clean)} rows")

# ── Aggregate by location ─────────────────────────────────
agg = df_clean.groupby('location').agg(
    avg_rate_per_m2 = ('price_per_m2', 'median'),
    min_rate        = ('price_per_m2', lambda x: x.quantile(0.20)),
    max_rate        = ('price_per_m2', lambda x: x.quantile(0.80)),
    count           = ('price_per_m2', 'count'),
).reset_index()

agg = agg[agg['count'] >= 5].copy()
agg['avg_rate_per_m2'] = agg['avg_rate_per_m2'].round(0).astype(int)
agg['min_rate']        = agg['min_rate'].round(0).astype(int)
agg['max_rate']        = agg['max_rate'].round(0).astype(int)
print(f"   Locations with 5+ listings: {len(agg)}")

# ── GPS Coordinates ───────────────────────────────────────
LOCATION_COORDS = {
    'Whitefield':                    (12.9698, 77.7500),
    'Sarjapur  Road':                (12.9070, 77.6860),
    'Sarjapur Road':                 (12.9070, 77.6860),
    'Electronic City':               (12.8399, 77.6770),
    'Electronic City Phase II':      (12.8299, 77.6770),
    'Marathahalli':                  (12.9591, 77.7001),
    'Hebbal':                        (13.0350, 77.5970),
    'KR Puram':                      (13.0007, 77.6929),
    'Rajaji Nagar':                  (12.9900, 77.5530),
    'Bannerghatta Road':             (12.8900, 77.5970),
    'Yeshwanthpur':                  (13.0200, 77.5500),
    'Hennur Road':                   (13.0481, 77.6388),
    'Thanisandra':                   (13.0614, 77.6262),
    'Horamavu':                      (13.0310, 77.6530),
    'Yelahanka':                     (13.1007, 77.5963),
    'Uttarahalli':                   (12.8900, 77.5450),
    'Nagarbhavi':                    (12.9600, 77.5070),
    'Vijayanagar':                   (12.9718, 77.5272),
    'Koramangala':                   (12.9352, 77.6245),
    'Indiranagar':                   (12.9784, 77.6408),
    'HSR Layout':                    (12.9116, 77.6389),
    'BTM Layout':                    (12.9166, 77.6101),
    'Jayanagar':                     (12.9308, 77.5838),
    'JP Nagar':                      (12.9102, 77.5857),
    'Banashankari':                  (12.9255, 77.5468),
    'Malleshwaram':                  (13.0035, 77.5680),
    'Domlur':                        (12.9609, 77.6391),
    'Banaswadi':                     (13.0197, 77.6539),
    'RT Nagar':                      (13.0201, 77.5925),
    'Kalyan Nagar':                  (13.0300, 77.6500),
    'Mahadevapura':                  (12.9946, 77.7122),
    'Kadugodi':                      (12.9834, 77.7832),
    'Varthur':                       (12.9392, 77.7482),
    'Hoodi':                         (12.9929, 77.7201),
    'Kengeri':                       (12.9063, 77.4822),
    'Begur Road':                    (12.8650, 77.6150),
    'Bommanahalli':                  (12.8980, 77.6380),
    'Harlur':                        (12.9050, 77.6700),
    'Bellandur':                     (12.9257, 77.6757),
    'Haralur Road':                  (12.8968, 77.6791),
    'Chandapura':                    (12.8300, 77.6850),
    'Devanahalli':                   (13.2448, 77.7143),
    'Hoskote':                       (13.0712, 77.7988),
    'Anekal':                        (12.7130, 77.6960),
    'Old Madras Road':               (12.9900, 77.6800),
    'Cunningham Road':               (12.9800, 77.5950),
    'MG Road':                       (12.9757, 77.6097),
    'Old Airport Road':              (12.9600, 77.6600),
    'Outer Ring Road':               (12.9200, 77.6800),
    'Mysore Road':                   (12.9500, 77.5000),
    'Hosur Road':                    (12.8700, 77.6500),
    'Tumkur Road':                   (13.0500, 77.5200),
    'Jakkur':                        (13.0700, 77.6000),
    'Ramamurthy Nagar':              (13.0100, 77.6700),
    'Nagavara':                      (13.0500, 77.6200),
    'Brookefield':                   (12.9800, 77.7500),
    'ITPL':                          (12.9860, 77.7480),
    'Panathur':                      (12.9350, 77.7100),
    'Carmelram':                     (12.9050, 77.7100),
    'Gunjur':                        (12.9100, 77.7500),
    'Bidarahalli':                   (13.0200, 77.8000),
    'Budigere':                      (13.0900, 77.7800),
    'Vidyaranyapura':                (13.0700, 77.5400),
    'Sahakar Nagar':                 (13.0400, 77.5900),
    'HBR Layout':                    (13.0300, 77.6450),
    'Kammanahalli':                  (13.0100, 77.6600),
    'CV Raman Nagar':                (12.9840, 77.6640),
    'Frazer Town':                   (12.9900, 77.6200),
    'Shivaji Nagar':                 (12.9860, 77.6050),
    'Langford Town':                 (12.9530, 77.6000),
    'Richmond Town':                 (12.9632, 77.6051),
    'Sadashivanagar':                (13.0100, 77.5750),
    'Vasanth Nagar':                 (12.9900, 77.5900),
    'Dollars Colony':                (13.0400, 77.5700),
    'Sanjaynagar':                   (13.0200, 77.5850),
    'Basavanagudi':                  (12.9430, 77.5750),
    'Padmanabhanagar':               (12.9250, 77.5530),
    'RR Nagar':                      (12.9200, 77.5150),
    'Kanakapura Road':               (12.9100, 77.5750),
    'Anjanapura':                    (12.8750, 77.5600),
    'Akshayanagar':                  (12.8880, 77.6150),
    '7th Phase JP Nagar':            (12.8900, 77.5800),
    '6th Phase JP Nagar':            (12.9000, 77.5850),
    '5th Phase JP Nagar':            (12.9050, 77.5870),
    '8th Phase JP Nagar':            (12.8800, 77.5750),
    'Hulimavu':                      (12.8950, 77.5950),
    'Arekere':                       (12.8980, 77.6050),
    'Gottigere':                     (12.8750, 77.5950),
    'Subramanyapura':                (12.9100, 77.5550),
    'Konanakunte':                   (12.9000, 77.5650),
    'Channasandra':                  (13.0100, 77.7100),
    'Garudacharpalya':               (13.0000, 77.7000),
    'Lakshminarayana Pura':          (12.9700, 77.6530),
    'Hennur':                        (13.0481, 77.6388),
    'Nandi Hills':                   (13.3700, 77.6830),
    'Attibele':                      (12.7780, 77.7640),
    'Sarjapura':                     (12.8600, 77.7800),
    'Dommasandra':                   (12.8900, 77.7400),
    'Begur':                         (12.8650, 77.6150),
    'Ayanagar':                      (12.8880, 77.5730),
    'Chamrajpet':                    (12.9630, 77.5650),
    'Shampura':                      (13.0000, 77.6500),
    'Babusapalya':                   (13.0200, 77.6450),
    'Kaggadasapura':                 (13.0000, 77.6750),
    'Amruthahalli':                  (13.0500, 77.5750),
    'Kothanur':                      (13.0650, 77.5950),
    'Choodasandra':                  (12.9100, 77.7200),
    'Hullahalli':                    (12.8300, 77.6200),
    'Judicial Layout':               (12.9200, 77.5750),
    'Kothannur':                     (13.0650, 77.5950),
    'Narayanapura':                  (13.0550, 77.6400),
    'TC Palaya':                     (13.0050, 77.7600),
}

# ── Match coordinates ─────────────────────────────────────
def get_coords(name):
    name = str(name).strip()
    if name in LOCATION_COORDS:
        return LOCATION_COORDS[name]
    for key, coords in LOCATION_COORDS.items():
        if key.lower() == name.lower():
            return coords
    for key, coords in LOCATION_COORDS.items():
        if key.lower() in name.lower() or name.lower() in key.lower():
            return coords
    return None

agg['location_clean'] = agg['location'].str.strip()
coords_series = agg['location_clean'].apply(get_coords)
agg['lat'] = coords_series.apply(lambda x: x[0] if x else np.nan)
agg['lng'] = coords_series.apply(lambda x: x[1] if x else np.nan)

before = len(agg)
agg    = agg.dropna(subset=['lat', 'lng'])
print(f"   Locations matched with GPS: {len(agg)} (dropped {before - len(agg)} unknown)")

# ── Zone type ─────────────────────────────────────────────
COMMERCIAL = ['MG Road','Brigade Road','Cunningham Road','Richmond Town',
              'Old Airport Road','Outer Ring Road','Mysore Road',
              'Yeshwanthpur','Shivaji Nagar','Frazer Town']
INDUSTRIAL = ['Electronic City','Peenya','Tumkur Road','Hosur Road',
              'Bommanahalli','Doddaballapur']

def assign_zone(name):
    for a in COMMERCIAL:
        if a.lower() in name.lower(): return 'commercial'
    for a in INDUSTRIAL:
        if a.lower() in name.lower(): return 'industrial'
    return 'residential'

agg['zone_type'] = agg['location_clean'].apply(assign_zone)

# ── Tier ──────────────────────────────────────────────────
def assign_tier(rate):
    if rate >= 75000: return 'premium'
    elif rate >= 40000: return 'mid'
    else: return 'affordable'

agg['tier'] = agg['avg_rate_per_m2'].apply(assign_tier)

# ── Final output ──────────────────────────────────────────
final = agg[[
    'location_clean','lat','lng','zone_type',
    'avg_rate_per_m2','min_rate','max_rate',
    'tier','count'
]].copy()

final.columns = [
    'area_name','lat','lng','zone_type',
    'avg_rate_per_m2','min_rate','max_rate',
    'tier','listing_count'
]

final = final.sort_values('avg_rate_per_m2', ascending=False).reset_index(drop=True)
final.to_csv(OUT_PATH, index=False)

print(f"\n✅ Saved {len(final)} real locations to bengaluru_land_rates.csv")
print(f"\n📊 Tier breakdown:")
print(f"   Premium    : {len(final[final['tier']=='premium'])}")
print(f"   Mid        : {len(final[final['tier']=='mid'])}")
print(f"   Affordable : {len(final[final['tier']=='affordable'])}")
print(f"\n💰 Rate range:")
print(f"   Max: ₹{final['avg_rate_per_m2'].max():,}/m²  — {final.iloc[0]['area_name']}")
print(f"   Min: ₹{final['avg_rate_per_m2'].min():,}/m²  — {final.iloc[-1]['area_name']}")
print(f"\n📋 Top 10 areas:")
print(final[['area_name','avg_rate_per_m2','tier','listing_count']].head(10).to_string(index=False))