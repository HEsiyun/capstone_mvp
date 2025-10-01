"""
merge_to_assets_master.py
合并表：
- assets.csv
- asset_condition.csv
- asset_photos.csv
- costs.csv
输出：
- assets_master.csv
功能：
- 仅保留每个资产最近一次 condition / photo
- 生成统一字段（含 GIS、条件、照片、成本等）
- 缺图时在 sample_images_placeholder/ 下生成灰度占位图，并更新 photo_uri
"""

import os
from pathlib import Path
from datetime import datetime
import pandas as pd
from PIL import Image, ImageDraw

# === 配置区 ===
BASE = Path(".")  # 数据文件所在目录；如需指定绝对路径，改成 Path("/path/to/data")
OUT_MASTER = BASE / "assets_master.csv"
PLACEHOLDER_DIR = BASE / "sample_images_placeholder"
GENERATE_PLACEHOLDER = True  # 需要时生成灰度占位图

def _read_csv_or_none(path: Path):
    return pd.read_csv(path) if path.exists() else None

def _parse_date_cols(df: pd.DataFrame, col: str):
    if df is not None and col in df.columns:
        df[col] = pd.to_datetime(df[col], errors="coerce")

def _latest_per_asset(df: pd.DataFrame, time_col: str) -> pd.DataFrame:
    """按 asset_id + 时间列倒序，取每个资产的一条最新记录。"""
    if df is None or time_col not in df.columns:
        return df
    sorted_df = df.sort_values(["asset_id", time_col], ascending=[True, False])
    return sorted_df.groupby("asset_id", as_index=False).first()

def _is_valid_file_uri(uri: str) -> bool:
    if not isinstance(uri, str) or not uri:
        return False
    p = Path(uri.replace("file://", "")) if uri.startswith("file://") else Path(uri)
    return p.exists()

def _ensure_placeholder(asset_id: str, asset_type: str) -> str:
    """生成灰度占位图并返回 file:// 路径"""
    PLACEHOLDER_DIR.mkdir(exist_ok=True)
    fn = f"IMG_{asset_id}.png"
    path = PLACEHOLDER_DIR / fn
    if not path.exists():
        img = Image.new("L", (640, 360), color=210)
        d = ImageDraw.Draw(img)
        text = f"{asset_id}\n{asset_type or 'asset'}"
        d.multiline_text((20, 20), text, fill=0, spacing=6)
        img.save(path)
    return f"file://{path}"

def merge_to_master(base: Path = BASE, generate_placeholder: bool = True) -> Path:
    # 1) 读入各表（不存在则返回 None）
    assets = _read_csv_or_none(base / "assets.csv")
    conds  = _read_csv_or_none(base / "asset_condition.csv")
    photos = _read_csv_or_none(base / "asset_photos.csv")
    costs  = _read_csv_or_none(base / "costs.csv")

    # 兜底：如果 assets 缺失，尽力从 photos 派生最小表（保证能合成）
    if assets is None and photos is not None:
        ids = sorted(photos["asset_id"].unique())
        assets = pd.DataFrame({
            "asset_id": ids,
            "type": ["unknown"] * len(ids),
            "sub_type": ["unknown"] * len(ids),
            "park_id": ["PARK_UNKNOWN"] * len(ids),
            "park_name": ["Unknown Park"] * len(ids),
            "lon": [None] * len(ids),
            "lat": [None] * len(ids),
            "geom_wkt": [None] * len(ids),
            "install_date": ["2018-01-01"] * len(ids),
            "criticality": ["medium"] * len(ids),
            "last_visit_at": [pd.NaT] * len(ids),
        })

    # 若 condition/costs 缺失，建立占位
    if conds is None and assets is not None:
        conds = pd.DataFrame({
            "asset_id": assets["asset_id"],
            "assessed_at": [pd.NaT] * len(assets),
            "source": ["manual"] * len(assets),
            "condition": ["unknown"] * len(assets),
            "score": [None] * len(assets),
            "notes": ["" ] * len(assets),
        })
    if costs is None and assets is not None:
        costs = pd.DataFrame({
            "asset_id": assets["asset_id"],
            "replacement_cost": [None] * len(assets),
            "last_updated_at": [pd.NaT] * len(assets),
        })

    if photos is None:
        raise FileNotFoundError("asset_photos.csv 缺失：至少需要它来构建最小可用的 master 表。")

    # 2) 解析日期列
    _parse_date_cols(assets, "last_visit_at")
    _parse_date_cols(conds, "assessed_at")
    _parse_date_cols(photos, "taken_at")
    _parse_date_cols(costs, "last_updated_at")

    # 3) 仅保留最近一次的 condition / photo
    latest_cond  = _latest_per_asset(conds,  "assessed_at")
    latest_photo = _latest_per_asset(photos, "taken_at")

    # 4) 合并
    m = assets.merge(latest_cond,  on="asset_id", how="left", suffixes=("", "_cond"))
    m = m.merge(latest_photo,      on="asset_id", how="left", suffixes=("", "_photo"))
    m = m.merge(costs,             on="asset_id", how="left", suffixes=("", "_cost"))

    # 5) 统一字段名 + 派生列
    m["asset_type"] = (m["type"].astype(str) + "_" + m["sub_type"].astype(str)).str.replace(r"\s+", "_", regex=True)
    m.rename(columns={
        "assessed_at": "condition_assessed_at",
        "source": "condition_source",
        "condition": "condition_label",
        "score": "condition_score",
        "notes": "condition_notes",
        "photo_id": "photo_id",
        "uri": "photo_uri",
        "taken_at": "photo_taken_at",
        "taken_by": "photo_taken_by",
        "labels_json": "photo_labels_json",
        "replacement_cost": "replacement_cost",
        "last_updated_at": "cost_last_updated_at",
    }, inplace=True)

    # 6) 列顺序（尽量齐）
    cols_order = [
        "asset_id", "asset_type", "type", "sub_type",
        "park_id", "park_name", "lon", "lat", "geom_wkt", "criticality",
        "install_date", "last_visit_at",
        "condition_label", "condition_score", "condition_source", "condition_notes", "condition_assessed_at",
        "photo_id", "photo_uri", "photo_taken_at", "photo_taken_by", "photo_labels_json",
        "replacement_cost", "cost_last_updated_at"
    ]
    cols_order = [c for c in cols_order if c in m.columns]
    m = m[cols_order].copy()

    # 7) 缺失/无效图片时生成灰度占位图
    if generate_placeholder:
        def fill_photo_uri(row):
            uri = row.get("photo_uri", "")
            if _is_valid_file_uri(uri):
                return uri
            return _ensure_placeholder(row["asset_id"], row.get("asset_type", "asset"))
        m["photo_uri"] = m.apply(fill_photo_uri, axis=1)

    # 8) 保存
    m.to_csv(OUT_MASTER, index=False)
    print(f"✅ Wrote {OUT_MASTER} (rows={len(m)})")
    return OUT_MASTER

if __name__ == "__main__":
    merge_to_master(BASE, GENERATE_PLACEHOLDER)