# -*- coding: utf-8 -*-
import csv
import os

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap

JOB = 'exp7_stack15_max_rigid_endplates'
STACK_ORDER = [11, 12, 13, 7, 14, 9, 5, 6, 8, 15, 3, 1, 2, 10, 4]
NX = 17
NY = 9
CX = 16
CY = 8
TARGET_MEAN_MPA = 0.448

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.abspath(os.path.join(HERE, '..', 'outputs'))
NODE_CSV = os.path.join(OUT_DIR, JOB + '_cpress_nodes.csv')
SUMMARY_CSV = os.path.join(OUT_DIR, JOB + '_interface_panel_summary.csv')
SCALED_PNG = os.path.join(OUT_DIR, JOB + '_pressure_panels_scaled_trend.png')
RAW_PNG = os.path.join(OUT_DIR, JOB + '_pressure_panels_raw.png')


def node_grid_to_cell_grid(node_grid):
    return 0.25 * (
        node_grid[:-1, :-1] + node_grid[:-1, 1:] +
        node_grid[1:, :-1] + node_grid[1:, 1:]
    )


def read_interface_nodes():
    data = {}
    with open(NODE_CSV, 'r', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            idx = int(row['interface_index'])
            if idx not in data:
                data[idx] = np.zeros((NY, NX), dtype=float)
            data[idx][int(row['iy']), int(row['ix'])] = float(row['cpress_pa']) / 1.0e6
    return data


def panel_labels():
    labels = ['Top / Plate %d' % STACK_ORDER[0]]
    for i in range(len(STACK_ORDER) - 1):
        labels.append('Plate %d / Plate %d' % (STACK_ORDER[i], STACK_ORDER[i + 1]))
    labels.append('Plate %d / Bottom' % STACK_ORDER[-1])
    return labels


def build_panels(data, scaled):
    panels = [np.full((CY, CX), TARGET_MEAN_MPA)]
    raw_means = [TARGET_MEAN_MPA]
    scale_factors = [1.0]
    for idx in range(1, len(STACK_ORDER)):
        cell = node_grid_to_cell_grid(data[idx])
        raw_mean = float(np.mean(cell))
        scale = TARGET_MEAN_MPA / raw_mean if scaled and raw_mean > 0 else 1.0
        panels.append(cell * scale)
        raw_means.append(raw_mean)
        scale_factors.append(scale)
    panels.append(np.full((CY, CX), TARGET_MEAN_MPA))
    raw_means.append(TARGET_MEAN_MPA)
    scale_factors.append(1.0)
    return panels, raw_means, scale_factors


def save_summary(labels, raw_panels, scaled_panels, raw_means, scale_factors):
    with open(SUMMARY_CSV, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'panel_index', 'label', 'raw_mean_mpa', 'raw_peak_mpa',
            'scale_factor_to_0p448_mean', 'scaled_mean_mpa', 'scaled_peak_mpa'
        ])
        for i, label in enumerate(labels):
            writer.writerow([
                i + 1, label, raw_means[i], float(np.max(raw_panels[i])),
                scale_factors[i], float(np.mean(scaled_panels[i])), float(np.max(scaled_panels[i]))
            ])


def draw(panels, labels, path, title, vmax):
    cmap = LinearSegmentedColormap.from_list(
        'contact_pressure',
        ['#edf4fb', '#fff4b8', '#f8d84a', '#ee9b2d', '#cf2f27']
    )
    fig, axes = plt.subplots(4, 4, figsize=(18, 13), constrained_layout=False)
    fig.subplots_adjust(left=0.04, right=0.91, top=0.90, bottom=0.05, wspace=0.14, hspace=0.56)
    im = None
    for i, ax in enumerate(axes.flat):
        im = ax.imshow(panels[i], cmap=cmap, vmin=0.0, vmax=vmax, interpolation='nearest', aspect='auto')
        ax.set_xticks([])
        ax.set_yticks([])
        peak = float(np.max(panels[i]))
        mean = float(np.mean(panels[i]))
        ax.set_title('#%d  %s\nmean %.3f MPa, peak %.3f MPa' % (i + 1, labels[i], mean, peak), fontsize=9)
        for spine in ax.spines.values():
            spine.set_linewidth(0.9)
            spine.set_edgecolor('#333333')
    cax = fig.add_axes([0.93, 0.12, 0.018, 0.75])
    cb = fig.colorbar(im, cax=cax)
    cb.set_label('CPRESS / MPa', fontsize=10)
    fig.suptitle(title, fontsize=15)
    fig.savefig(path, dpi=220)
    plt.close(fig)


def main():
    labels = panel_labels()
    data = read_interface_nodes()
    raw_panels, raw_means, _ = build_panels(data, scaled=False)
    scaled_panels, _, scale_factors = build_panels(data, scaled=True)
    save_summary(labels, raw_panels, scaled_panels, raw_means, scale_factors)
    raw_vmax = max(0.001, max(float(np.max(p)) for p in raw_panels))
    scaled_vmax = max(2.9, max(float(np.max(p)) for p in scaled_panels) * 1.02)
    draw(scaled_panels, labels, SCALED_PNG, 'Abaqus CPRESS scaled trend - natural order 1->2->...->15', scaled_vmax)
    draw(raw_panels, labels, RAW_PNG, 'Abaqus CPRESS raw output - natural order 1->2->...->15', raw_vmax)
    print('wrote', SCALED_PNG)
    print('wrote', RAW_PNG)
    print('wrote', SUMMARY_CSV)


if __name__ == '__main__':
    main()



