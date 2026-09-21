"""Tests for multimodal water segmentation and speckle filtering."""

import numpy as np
import rasterio
from rasterio.transform import from_origin

from src.segmentation import (
    compute_otsu_threshold,
    load_aux_priors,
    load_config,
    refined_lee_filter,
    segment_optical,
    segment_water,
    speckle_filter,
)


def test_load_config_defaults(tmp_path):
    # Test load_config with non-existent file falls back to defaults
    cfg = load_config(tmp_path / "non_existent.yaml")
    assert "otsu_min_db" in cfg
    assert cfg["otsu_min_db"] == -22.0
    assert cfg["mmu_min_pixels"] == 25

    # Test load_config with custom file
    custom_yaml = tmp_path / "custom.yaml"
    custom_yaml.write_text("otsu_min_db: -25.0\nmmu_min_pixels: 50\n", encoding="utf-8")
    cfg_custom = load_config(custom_yaml)
    assert cfg_custom["otsu_min_db"] == -25.0
    assert cfg_custom["mmu_min_pixels"] == 50
    assert cfg_custom["slope_max_deg"] == 5.0  # default filled in


def test_refined_lee_filter_basic():
    # Constant data: filtered should match input
    data = np.full((20, 20), -15.0, dtype=np.float32)
    filtered = refined_lee_filter(data, size=5)
    assert filtered.shape == (20, 20)
    assert np.allclose(filtered, -15.0, atol=0.1)

    # Edge case: all invalid (e.g. nodata -999.0)
    invalid = np.full((10, 10), -999.0, dtype=np.float32)
    filtered_inv = refined_lee_filter(invalid)
    assert np.array_equal(filtered_inv, invalid)

    # Partially invalid
    data[0, 0] = -999.0
    filtered_part = refined_lee_filter(data, size=5)
    assert filtered_part[0, 0] == -999.0


def test_speckle_filter_methods():
    arr = np.random.uniform(-25.0, -10.0, (15, 15)).astype(np.float32)
    arr[0, 0] = np.nan

    assert speckle_filter(None) is None

    # Lee
    res_lee = speckle_filter(arr, method="lee", size=5)
    assert res_lee.shape == arr.shape

    # Median
    res_med = speckle_filter(arr, method="median", size=5)
    assert res_med.shape == arr.shape

    # Uniform
    res_uni = speckle_filter(arr, method="uniform", size=5)
    assert res_uni.shape == arr.shape

    # All invalid
    all_nan = np.full((5, 5), np.nan, dtype=np.float32)
    res_nan = speckle_filter(all_nan, method="uniform")
    assert np.all(np.isnan(res_nan))


def test_compute_otsu_threshold():
    # Bimodal distribution: water around -20 dB, land around -14 dB
    rng = np.random.default_rng(42)
    water_vals = rng.normal(-20.0, 0.5, 500)
    land_vals = rng.normal(-14.5, 0.5, 500)
    data = np.concatenate([water_vals, land_vals]).reshape((20, 50)).astype(np.float32)

    th = compute_otsu_threshold(data)
    assert -21.0 < th < -15.0

    # With mask
    mask = np.zeros(data.shape, dtype=bool)
    mask[:, :25] = True
    th_masked = compute_otsu_threshold(data, mask=mask)
    assert -22.0 <= th_masked <= -14.5

    # Small array (< 50 valid pixels) -> fallback -16.5
    tiny = np.full((5, 5), -18.0, dtype=np.float32)
    assert compute_otsu_threshold(tiny) == -16.5


def test_load_aux_priors(tmp_path):
    aux_path = tmp_path / "test_aux.tif"
    transform = from_origin(127.0, 50.0, 10.0, 10.0)
    crs = "EPSG:32652"

    # Create dummy 6-band GeoTIFF
    # band 1: slope, band 2: hand, band 3: occurrence, band 6: builtup
    data = np.zeros((6, 20, 20), dtype=np.float32)
    data[0, :, :] = 2.0  # slope 2 deg <= 5
    data[1, :, :] = 10.0  # hand 10m <= 25
    data[2, :, :] = 90.0  # occurrence 90% >= 80% (permanent)
    data[5, :, :] = 0.0  # builtup 0 < 0.5

    with rasterio.open(
        aux_path,
        "w",
        driver="GTiff",
        height=20,
        width=20,
        count=6,
        dtype=np.float32,
        crs=crs,
        transform=transform,
    ) as dst:
        dst.write(data)

    res = load_aux_priors(aux_path, target_shape=(20, 20), target_transform=transform, target_crs=crs)
    assert "topo_mask" in res
    assert "permanent_mask" in res
    assert res["topo_mask"].all()
    assert res["permanent_mask"].all()


def test_segment_optical(tmp_path):
    # Non-existent path
    w, v = segment_optical(tmp_path / "absent.tif", (10, 10))
    assert w is None
    assert not np.any(v)

    # File with fewer than 8 bands
    short_tif = tmp_path / "short.tif"
    transform = from_origin(127.0, 50.0, 10.0, 10.0)
    with rasterio.open(
        short_tif,
        "w",
        driver="GTiff",
        height=10,
        width=10,
        count=4,
        dtype=np.float32,
        crs="EPSG:32652",
        transform=transform,
    ) as dst:
        dst.write(np.zeros((4, 10, 10), dtype=np.float32))

    w, v = segment_optical(short_tif, (10, 10))
    assert w is None
    assert not np.any(v)

    # Valid 8-band raster
    opt_tif = tmp_path / "valid_s2.tif"
    s2_data = np.full((8, 10, 10), -999.0, dtype=np.float32)
    # Band 6 (index 5): MNDWI, Band 7 (index 6): NDVI, Band 8 (index 7): AWEIsh
    # Pixel (2, 2) is clear water: MNDWI=0.3 (>0.1), NDVI=0.1 (<=0.3), AWEIsh=0.2 (>0.0)
    s2_data[5, 2, 2] = 0.3
    s2_data[6, 2, 2] = 0.1
    s2_data[7, 2, 2] = 0.2

    # Pixel (4, 4) is vegetation: MNDWI=-0.2, NDVI=0.8, AWEIsh=-0.5
    s2_data[5, 4, 4] = -0.2
    s2_data[6, 4, 4] = 0.8
    s2_data[7, 4, 4] = -0.5

    with rasterio.open(
        opt_tif,
        "w",
        driver="GTiff",
        height=10,
        width=10,
        count=8,
        dtype=np.float32,
        crs="EPSG:32652",
        transform=transform,
    ) as dst:
        dst.write(s2_data)

    water_mask, valid_mask = segment_optical(opt_tif, (10, 10))
    assert valid_mask[2, 2]
    assert valid_mask[4, 4]
    assert not valid_mask[0, 0]  # nodata
    assert water_mask[2, 2]
    assert not water_mask[4, 4]


def test_segment_water_comprehensive():
    shape = (30, 30)
    # Background SAR: land at -12 dB, water patch at -22 dB
    vv = np.full(shape, -12.0, dtype=np.float32)
    vv[10:20, 10:20] = -22.0
    vh = vv - 6.0

    # 1. Pre date segmentation with Otsu
    water_pre = segment_water(
        vv=vv,
        vh=vh,
        is_peak=False,
        use_topo=False,
        use_optical=False,
        use_mmu=False,
        use_permanent=False,
    )
    assert water_pre[15, 15] == 1
    assert water_pre[0, 0] == 0

    # 2. Peak date with drop detection
    vv_peak = np.full(shape, -12.0, dtype=np.float32)
    vv_peak[10:20, 10:20] = -22.0  # pre water
    vv_peak[22:28, 22:28] = -18.0  # flooded: was -12 in ref, now -18 -> drop = 6 dB >= 3 dB
    vh_peak = vv_peak - 6.0

    water_peak = segment_water(
        vv=vv_peak,
        vh=vh_peak,
        vv_ref=vv,
        vh_ref=vh,
        is_peak=True,
        use_topo=False,
        use_optical=False,
        use_mmu=False,
        use_permanent=False,
    )
    assert water_peak[25, 25] == 1

    # 3. Double-bounce detection under canopy
    vv_db = np.full(shape, -16.0, dtype=np.float32)
    vh_ref = np.full(shape, -22.0, dtype=np.float32)
    vh_db = np.full(shape, -18.0, dtype=np.float32)  # delta_vh = +4 dB >= 2.0 dB
    hand = np.full(shape, 1.0, dtype=np.float32)
    slope = np.full(shape, 1.0, dtype=np.float32)
    builtup = np.zeros(shape, dtype=np.float32)

    water_db = segment_water(
        vv=vv_db,
        vh=vh_db,
        vv_ref=vv_db,
        vh_ref=vh_ref,
        hand=hand,
        slope=slope,
        builtup=builtup,
        is_peak=True,
        use_topo=False,
        use_optical=False,
        use_mmu=False,
        use_permanent=False,
    )
    assert water_db[5, 5] == 1

    # 4. Partial / nodata SAR fallback
    sar_nodata = np.full(shape, -999.0, dtype=np.float32)
    permanent_mask = np.zeros(shape, dtype=bool)
    permanent_mask[5:8, 5:8] = True
    topo_mask = np.ones(shape, dtype=bool)
    occ = np.full(shape, 10.0, dtype=np.float32)

    water_fallback = segment_water(
        vv=sar_nodata,
        permanent_mask=permanent_mask,
        topo_mask=topo_mask,
        hand=hand,
        occurrence=occ,
        is_peak=True,
        use_permanent=True,
        use_mmu=False,
    )
    assert np.all(water_fallback[5:8, 5:8] == 1)

    # 5. Optical fusion
    opt_water = np.zeros(shape, dtype=bool)
    opt_water[2, 2] = True
    opt_valid = np.zeros(shape, dtype=bool)
    opt_valid[2, 2] = True

    fused = segment_water(
        vv=vv,
        optical_water=opt_water,
        optical_valid=opt_valid,
        use_optical=True,
        use_topo=False,
        use_mmu=False,
    )
    assert fused[2, 2] == 1
