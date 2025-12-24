#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Nov 22 10:50:12 2025

@author: macbuil
"""

# Planisphère avec ajustement du niveau moyen ((moyenne du signal à R=0,75)) 

import numpy as np
#import imageio.v2 as imageio
import matplotlib.pyplot as plt
import os
from scipy.ndimage import map_coordinates

# -------------------------------------------------------------------
# PARAMÈTRES GÉNÉRAUX
# -------------------------------------------------------------------

BASE_PATH = "/Users/macbuil/Documents/plani/"
OUTPUT_PLANISPHERE = os.path.join(BASE_PATH, "_plani.png")
OUTPUT_DISK = os.path.join(BASE_PATH, "_disk.png")

# [filename, L(deg), B(deg), R(pixels), xc, yc, V1, V2, do_limb_correction]
# finalename = nom du fichier image
# L = Longitude du méridien central
# B = Latitude du méridien central
# R = Rayon du disque
# xc, yc = coordonnées du centre du disque en pixels
# (V1, V2) = angles sélectionnées de part et d'autre du méridien central
# do_limb_correction = correction assombrissement centre-bord
"""
IMAGE_INFO = [
   ("a1_d.png", 161.53, -2.25, 410, 550, 550, 7.5, 80, True),
   ("a2_d.png", 148.97, -2.37, 410, 550, 550, 7.5, 7.5,  True),
   ("a3_d.png", 136.33, -2.49, 410, 550, 550, 15, 7.5, True),
   #("a4_d.png", 122.53, -2.61, 410, 550, 550, 7.5, 7.5, True),
   ("a5_d.png", 109.40, -2.73, 410, 550, 550, 7.5, 15, True),
   ("a6_d.png", 95.3, -2.86, 410, 550, 550, 7.5, 7.5, True),
   ("a7_d.png", 83.88, -2.96, 410, 550, 550, 7.5, 7.5, True),
   ("a8_d.png", 68.80, -3.09, 410, 550, 550, 80, 7.5, True),
]
"""

'''
IMAGE_INFO = [
   ("a1_d.png", 161.53, -2.25, 410, 550, 550, 60, 80, True),
   ("a2_d.png", 148.97, -2.37, 410, 550, 550, 60, 60,  True),
   ("a3_d.png", 136.33, -2.49, 410, 550, 550, 60, 60, True),
   ("a4_d.png", 122.53, -2.61, 410, 550, 550, 60, 60, True),
   ("a5_d.png", 109.40, -2.73, 410, 550, 550, 60, 60, True),
   ("a6_d.png", 95.3, -2.86, 410, 550, 550, 60, 60, True),
   ("a7_d.png", 83.88, -2.96, 410, 550, 550, 60, 60, True),
   ("a8_d.png", 68.80, -3.09, 410, 550, 550, 80, 60, True),
]
'''


#W = 1200
#H = 600
#L0 = 0.0 # origine planisphère
projection_type = 'orthographic'  # 'orthographic', 'mercator', 'lambert'


# -------------------------------------------------------------------
# CORRECTION CENTRE → BORD
# -------------------------------------------------------------------

def correct_center_to_limb(img, xc, yc, R):
    h, w = img.shape
    y, x = np.indices((h, w))
    r = np.sqrt((x - xc)**2 + (y - yc)**2)
    mask = r <= 0.95 * R
    r_m = r[mask]
    I_m = img[mask]

    if len(r_m) < 100:
        return img

    nb = 200
    rbins = np.linspace(0, r_m.max(), nb+1)
    rc = 0.5 * (rbins[:-1] + rbins[1:])
    prof = np.zeros(nb)

    for i in range(nb):
        sel = (r_m >= rbins[i]) & (r_m < rbins[i+1])
        if np.any(sel):
            prof[i] = np.median(I_m[sel])
        else:
            prof[i] = prof[i-1] if i > 0 else I_m[0]

    poly = np.poly1d(np.polyfit(rc, prof, 4))
    correction = poly(r)
    I0 = poly(0)
    min_corr = 0.30 * I0
    correction = np.maximum(correction, min_corr)
    img_corr = img / correction * I0

    return img_corr.astype(np.float64)

def correct_center_to_limb_fast_0(img, xc, yc, R, nb=200):

    h, w = img.shape

    # --- indices (une seule fois) ---
    y, x = np.indices((h, w))
    r = np.hypot(x - xc, y - yc)

    mask = r <= (0.95 * R)
    if np.count_nonzero(mask) < 100:
        return img.astype(np.float64)

    r_m = r[mask]
    I_m = img[mask]

    # --- binning radial ---
    rbins = np.linspace(0.0, r_m.max(), nb + 1)
    rc = 0.5 * (rbins[:-1] + rbins[1:])

    bin_idx = np.digitize(r_m, rbins) - 1
    bin_idx = np.clip(bin_idx, 0, nb - 1)

    prof = np.empty(nb, dtype=np.float64)

    # --- médiane par bin (une seule passe Python légère) ---
    for i in range(nb):
        sel = (bin_idx == i)
        if sel.any():
            prof[i] = np.median(I_m[sel])
        else:
            prof[i] = prof[i-1] if i > 0 else I_m[0]

    # --- ajustement polynomial ---
    poly = np.poly1d(np.polyfit(rc, prof, 4))

    correction = poly(r)
    I0 = poly(0.0)

    min_corr = 0.30 * I0
    np.maximum(correction, min_corr, out=correction)

    img_corr = img / correction * I0

    return img_corr.astype(np.float64)

def correct_center_to_limb_fast(img, xc, yc, R, y_idx, x_idx, nb=200):
    """
    Correction du centre au limbe d'une image solaire.
    y_idx, x_idx doivent être pré-calculés avec np.indices(img.shape)
    """

    mask = np.sqrt((x_idx - xc)**2 + (y_idx - yc)**2) <= 0.95 * R

    if np.count_nonzero(mask) < 100:
        return img.astype(np.float64)

    r_m = np.sqrt((x_idx[mask] - xc)**2 + (y_idx[mask] - yc)**2)
    I_m = img[mask]

    # --- binning radial ---
    rbins = np.linspace(0.0, r_m.max(), nb + 1)
    rc = 0.5 * (rbins[:-1] + rbins[1:])

    bin_idx = np.digitize(r_m, rbins) - 1
    bin_idx = np.clip(bin_idx, 0, nb - 1)

    prof = np.empty(nb, dtype=np.float64)

    for i in range(nb):
        sel = (bin_idx == i)
        if sel.any():
            prof[i] = np.median(I_m[sel])
        else:
            prof[i] = prof[i-1] if i > 0 else I_m[0]

    # --- ajustement polynomial ---
    poly = np.poly1d(np.polyfit(rc, prof, 4))
    r = np.hypot(x_idx - xc, y_idx - yc)
    correction = poly(r)
    I0 = poly(0.0)
    min_corr = 0.30 * I0
    np.maximum(correction, min_corr, out=correction)

    img_corr = img / correction * I0

    return img_corr.astype(np.float64)

# -------------------------------------------------------------------
# INTERPOLATION BILINÉAIRE
# -------------------------------------------------------------------

def bilinear(img, x, y):
    h, w = img.shape
    x0 = np.floor(x).astype(int)
    y0 = np.floor(y).astype(int)
    x1 = (x0 + 1)
    y1 = y0 + 1
   
    valid = (x0 >= 0) & (x1 < w) & (y0 >= 0) & (y1 < h)
    #valid = (y0 >= 0) & (y1 < h)
    out = np.zeros_like(x, dtype=float)
    if not np.any(valid):
        print("not valid")
        return out
    Ia = img[y0[valid], x0[valid]]
    Ib = img[y0[valid], x1[valid]]
    Ic = img[y1[valid], x0[valid]]
    Id = img[y1[valid], x1[valid]]
    wa = (x1[valid] - x[valid]) * (y1[valid] - y[valid])
    wb = (x[valid] - x0[valid]) * (y1[valid] - y[valid])
    wc = (x1[valid] - x[valid]) * (y[valid] - y0[valid])
    wd = (x[valid] - x0[valid]) * (y[valid] - y0[valid])
    out[valid] = Ia*wa + Ib*wb + Ic*wc + Id*wd

    return out

# -------------------------------------------------------------------
# PROJECTIONS
# -------------------------------------------------------------------

def inverse_projection(L_grid, B_grid, Lc, Bc, proj='orthographic'):
    if proj == 'orthographic':
        x = np.cos(B_grid) * np.sin(L_grid - Lc)
        y = np.sin(B_grid) * np.cos(Bc) - np.cos(B_grid)*np.cos(L_grid - Lc)*np.sin(Bc)
        z = np.sin(B_grid) * np.sin(Bc) + np.cos(B_grid)*np.cos(L_grid - Lc)*np.cos(Bc)
    elif proj == 'mercator':
        lat_eps = np.deg2rad(89.9)
        B_grid = np.clip(B_grid, -lat_eps, lat_eps)
        x = L_grid - Lc
        y = np.log(np.tan(np.pi/4 + B_grid/2))
        z = np.ones_like(x)
    elif proj == 'lambert':
        k = np.sqrt(2 / (1 + np.sin(Bc)*np.sin(B_grid) + np.cos(Bc)*np.cos(B_grid)*np.cos(L_grid - Lc)))
        x = k * np.cos(B_grid) * np.sin(L_grid - Lc)
        y = k * (np.cos(Bc)*np.sin(B_grid) - np.sin(Bc)*np.cos(B_grid)*np.cos(L_grid - Lc))
        z = np.ones_like(x)
    else:
        raise ValueError(f"Projection inconnue : {proj}")
    return x, y, z

# -------------------------------------------------------------------
# GRILLES
# -------------------------------------------------------------------

def plot_grid_on_planisphere(ax, L0, lon_max, lat_min, lat_max, step=10, color_lat='blue', color_lon='blue'):
    lats = np.arange(lat_min, lat_max+1, step)
    lons = np.arange(L0, lon_max+1, step)
    for lat in lats:
        ax.plot([L0, lon_max], [lat, lat], color=color_lat, linewidth=0.5)
    for lon in lons:
        ax.plot([lon, lon], [lat_min, lat_max], color=color_lon, linewidth=0.5)

def draw_coord_grid_on_disk(ax, xc, yc, R, L2_deg, B2_deg, step=10):
    Lc = np.deg2rad(L2_deg)
    Bc = np.deg2rad(B2_deg)
    lats = np.arange(-90, 91, step)
    lons = np.arange(0, 360, step)

    def plot_visible(x, y, visible_mask, color):
        if np.any(visible_mask):
            idx = np.where(~visible_mask)[0]
            segments = np.split(np.arange(len(x)), idx)
            for seg in segments:
                if len(seg) > 1:
                    ax.plot(x[seg]+xc, y[seg]+yc, color=color, linewidth=0.5)

    for lat_deg in lats:
        lat = np.deg2rad(lat_deg)
        phi = np.linspace(0, 2*np.pi, 400)
        cos_c = np.cos(lat)
        sin_c = np.sin(lat)
        cos_Bc = np.cos(Bc)
        sin_Bc = np.sin(Bc)
        z = sin_c * sin_Bc + cos_c * cos_Bc * np.cos(phi)
        visible = z >= 0
        x = R * cos_c * np.sin(phi)
        y = R * (sin_c * cos_Bc - cos_c * sin_Bc * np.cos(phi))
        plot_visible(x, y, visible, color='blue')

    for lon_deg in lons:
        lon = np.deg2rad(lon_deg)
        lat_vals = np.linspace(-np.pi/2, np.pi/2, 400)
        sin_lat = np.sin(lat_vals)
        cos_lat = np.cos(lat_vals)
        z = sin_lat * sin_Bc + cos_lat * cos_Bc * np.cos(lon-Lc)
        visible = z >= 0
        x = R * cos_lat * np.sin(lon - Lc)
        y = R * (sin_lat * cos_Bc - cos_lat * sin_Bc * np.cos(lon-Lc))
        plot_visible(x, y, visible, color='blue')

# -------------------------------------------------------------------
# PLANISPHÈRE
# -------------------------------------------------------------------


def build_planisphere(images, IMAGE_INFO,H,W,L0, save_with_grid=True):
    lon_deg = np.linspace(L0, L0 + 360.0, W, endpoint=False)
    lat_deg = np.linspace(-90.0, 90.0, H, endpoint=True)
    L_grid, B_grid = np.meshgrid(np.deg2rad(lon_deg), np.deg2rad(lat_deg))

    plani = np.zeros((H, W), dtype=np.float64)
    weight = np.zeros((H, W), dtype=np.float64)

    ref_mean = None
    h, w = images[0].shape
    y_idx, x_idx = np.indices((h, w))

    for i, item in enumerate(IMAGE_INFO):
        # Nouveaux paramètres V1 et V2
        fname, L, B, R, xc, yc, v1, v2, do_limb = item

        #img = imageio.imread(os.path.join(BASE_PATH, fname)).astype(np.float64)
        img=images[i]
        if img.ndim == 3:
            img = img[..., 0]
        if do_limb:
            
            img = correct_center_to_limb_fast(img, xc, yc, R, y_idx, x_idx)

        # Normalisation par le niveau moyen central
        y_idx, x_idx = np.indices(img.shape)
        r = np.sqrt((x_idx - xc)**2 + (y_idx - yc)**2)
        mask = r <= 0.75 * R
        img_mean = np.mean(img[mask])
        if i == 0:
            ref_mean = img_mean
        else:
            img *= (ref_mean / img_mean if img_mean != 0 else 1.0)

        # Projection
        Lc = np.deg2rad(L)
        Bc = np.deg2rad(B)
        x_proj, y_proj, z = inverse_projection(L_grid, B_grid, Lc, Bc, proj=projection_type)
        visible = z > 0

        # --- NOUVEAU FILTRE ANGULAIRE ASYMÉTRIQUE --- #
        dlon = (L_grid - Lc + np.pi) % (2*np.pi) - np.pi   # intervalle [-π, +π]
        mask_lon = (dlon >= -np.deg2rad(v1)) & (dlon <= np.deg2rad(v2))
        mask_total = visible & mask_lon
        # ------------------------------------------------

        if not np.any(mask_total):
            continue

        xp = xc + R * x_proj[mask_total]
        yp = yc - R * y_proj[mask_total]
        vals = bilinear(img, xp, yp)

        plani[mask_total] += vals * z[mask_total]
        weight[mask_total] += z[mask_total]

    final = np.zeros_like(plani)
    mask = weight > 0
    final[mask] = plani[mask] / weight[mask]
    
    
    """
    if save_with_grid:
        fig, ax = plt.subplots(figsize=(12,6))
        ax.imshow(final, cmap="gray", origin="lower",
                       extent=[L0, L0+360, -90, 90], vmin=0, vmax=np.max(final))
        plot_grid_on_planisphere(ax, L0, L0+360, -90, 90)
        plt.xlabel("Longitude (°)")
        plt.ylabel("Latitude (°)")
        plt.title(f"Planisphère solaire (V1={v1}°, V2={v2}°)")
        #plt.colorbar(im, ax=ax, label="Intensité")
        #plt.savefig(OUTPUT_PLANISPHERE, dpi=300)
        plt.show()
    """
    return final, lon_deg, lat_deg




def build_planisphere_fast(images, IMAGE_INFO, H, W, L0, save_with_grid=True):

    lon_deg = np.linspace(L0, L0 + 360.0, W, endpoint=False)
    lat_deg = np.linspace(-90.0, 90.0, H, endpoint=True)

    lon_rad = np.deg2rad(lon_deg)
    lat_rad = np.deg2rad(lat_deg)

    B_grid = lat_rad[:, None]

    plani = np.zeros((H, W), dtype=np.float64)
    weight = np.zeros((H, W), dtype=np.float64)

    ref_mean = None
    y_idx = x_idx = None

    for i, item in enumerate(IMAGE_INFO):
        fname, L, B, R, xc, yc, v1, v2, do_limb = item
        img = images[i]

        if img.ndim == 3:
            img = img[..., 0]
        if do_limb:
            img = correct_center_to_limb(img, xc, yc, R)

        if y_idx is None:
            y_idx, x_idx = np.indices(img.shape)

        r = np.hypot(x_idx - xc, y_idx - yc)
        mask = r <= (0.75 * R)
        img_mean = img[mask].mean()

        if i == 0:
            ref_mean = img_mean
        elif img_mean != 0:
            img *= ref_mean / img_mean

        v1r = np.deg2rad(v1)
        v2r = np.deg2rad(v2)
        Lc = np.deg2rad(L)
        Bc = np.deg2rad(B)

        dlon = (lon_rad - Lc + np.pi) % (2*np.pi) - np.pi
        cols = np.where((dlon >= -v1r) & (dlon <= v2r))[0]
        if cols.size == 0:
            continue

        L_sub = lon_rad[cols][None, :]

        x_proj, y_proj, z = inverse_projection(
            L_sub, B_grid, Lc, Bc, proj=projection_type
        )

        visible = z > 0
        if not np.any(visible):
            continue
        iy, ix = np.nonzero(visible)
        
        xp = xc + R * x_proj[visible]
        yp = yc - R * y_proj[visible]

        vals = map_coordinates(img, [yp, xp], order=1, mode='constant', cval=0.0)

        zloc = z[visible]
        plani[iy, cols[ix]] += vals * zloc
        weight[iy, cols[ix]] += zloc

    final = np.zeros_like(plani)
    m = weight > 0
    final[m] = plani[m] / weight[m]

    # 👉 RETOUR COMPLET
    if save_with_grid:
        return final, lon_deg, lat_deg
    else:
        return final


# -------------------------------------------------------------------
# RECONSTRUCTION DISQUE
# -------------------------------------------------------------------

def disk_from_planisphere(plani, H, W, lon_deg, lat_deg, L2_deg, B2_deg, R2, imax, jmax,
                          output_file=None, draw_grid_flag=True):
    y, x = np.indices((imax, jmax))
    xc, yc = (imax-1)/2, (jmax-1)/2
    r = np.sqrt((x - xc)**2 + (y - yc)**2)
    mask = r <= R2

    L_grid = np.zeros((imax, jmax))
    B_grid = np.zeros((imax, jmax))
    Lc = np.deg2rad(L2_deg)
    Bc = np.deg2rad(B2_deg)

    theta = np.arcsin(r[mask]/R2)
    phi = np.arctan2(y[mask]-yc, x[mask]-xc)
    
    B_grid[mask] = np.arcsin(np.cos(theta)*np.sin(Bc) + np.sin(theta)*np.cos(Bc)*np.sin(phi))
    L_grid[mask] = Lc + np.arctan2(np.sin(theta)*np.cos(phi),
                                   np.cos(theta)*np.cos(Bc) - np.sin(theta)*np.sin(Bc)*np.sin(phi))

    lon_map = np.deg2rad(lon_deg)
    lat_map = np.deg2rad(lat_deg)

    
    disk = np.zeros((imax, jmax), dtype=np.float64)
    
    # mettre les coordonnées seulement là où mask==True
    L_wrapped = (L_grid[mask] - lon_map[0]) % (2*np.pi)
    x_img = L_wrapped / (2*np.pi) * (W - 1)
    y_img = (B_grid[mask] - lat_map[0]) / (lat_map[-1] - lat_map[0]) * (H - 1)
    eps = 1e-6 
    x_img = np.clip(x_img, 0.0, (W - 1) - eps) 
    y_img = np.clip(y_img, 0.0, (H - 1) - eps)
    
    disk[mask] = bilinear(plani, x_img, y_img)
    
    """
    
    fig, ax = plt.subplots(figsize=(6,6))
    ax.imshow(disk, cmap="gray", origin="lower")
    if draw_grid_flag:
        draw_coord_grid_on_disk(ax, xc, yc, R2, L2_deg, B2_deg)
    plt.title(f"L={L2_deg}°, B={B2_deg}°")
    #plt.colorbar(im, ax=ax, label="Intensité")
    if output_file:
        plt.savefig(output_file, dpi=300)
    plt.show()
    """
    
    return disk

def disk_from_planisphere_fast(plani, H, W,
                               lon_deg, lat_deg,
                               L2_deg, B2_deg, R2,
                               imax, jmax,output_file=None, draw_grid_flag=True):
    """
    Projection d'un planisphère sur un disque
    Version optimisée NumPy + SciPy (sans pré-calcul géométrique)
    """

    # grille image
    y, x = np.indices((imax, jmax))
    xc = (imax - 1) * 0.5
    yc = (jmax - 1) * 0.5

    dx = x - xc
    dy = y - yc

    # rayon et masque disque
    r = np.hypot(dx, dy)
    mask = r <= R2

    disk = np.zeros((imax, jmax), dtype=np.float64)
    if not np.any(mask):
        return disk

    # extraction uniquement dans le disque
    r_m  = r[mask]
    dx_m = dx[mask]
    dy_m = dy[mask]

    # coordonnées sphériques
    theta = np.arcsin(r_m / R2)
    phi   = np.arctan2(dy_m, dx_m)

    # constantes
    Lc = np.deg2rad(L2_deg)
    Bc = np.deg2rad(B2_deg)

    sin_t = np.sin(theta)
    cos_t = np.cos(theta)
    sin_p = np.sin(phi)
    cos_p = np.cos(phi)

    sinBc = np.sin(Bc)
    cosBc = np.cos(Bc)

    # latitude / longitude projetées
    B = np.arcsin(
        cos_t * sinBc + sin_t * cosBc * sin_p
    )

    L = Lc + np.arctan2(
        sin_t * cos_p,
        cos_t * cosBc - sin_t * sinBc * sin_p
    )

    # conversion vers coordonnées image
    lon_map = np.deg2rad(lon_deg)
    lat_map = np.deg2rad(lat_deg)

    L = (L - lon_map[0]) % (2.0 * np.pi)

    x_img = L * (W - 1) / (2.0 * np.pi)
    y_img = (B - lat_map[0]) * (H - 1) / (lat_map[-1] - lat_map[0])

    # sécurité interpolation
    eps = 1e-6
    x_img = np.clip(x_img, 0.0, (W - 1) - eps)
    y_img = np.clip(y_img, 0.0, (H - 1) - eps)

    # interpolation bilinéaire SciPy
    # map_coordinates attend (ligne, colonne) = (y, x)
    coords = np.vstack((y_img, x_img))

    disk[mask] = map_coordinates(
        plani,
        coords,
        order=1,        # bilinéaire
        mode='wrap'     # longitude périodique
    )

    return disk

# -------------------------------------------------------------------
# MAIN
# -------------------------------------------------------------------

if __name__ == "__main__":
    plani, lon_deg, lat_deg = build_planisphere(save_with_grid=True)
    disk_from_planisphere(plani, lon_deg, lat_deg,
                          L2_deg=135.0, B2_deg=-40.0,
                          R2=380, imax=800, jmax=800,
                          output_file=OUTPUT_DISK,
                          draw_grid_flag=True)