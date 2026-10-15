"""Geometria do mascote em desktop com monitores independentes e coordenadas negativas.

Nenhum acesso a janelas de outros aplicativos. Todos os destinos ficam na
area util de um monitor real, inclusive quando ha espacos vazios entre telas.
"""
from __future__ import annotations

from collections.abc import Sequence

Rect = tuple[int, int, int, int]
Point = tuple[int, int]


def clamp_to_screens(point: Point, size: Point, screens: Sequence[Rect]) -> Point:
    """Encaixa um canto superior esquerdo no monitor mais proximo."""
    if not screens:
        return point
    width, height = max(1, int(size[0])), max(1, int(size[1]))
    px, py = int(point[0]), int(point[1])
    choices = []
    for x, y, sw, sh in screens:
        if sw <= 0 or sh <= 0:
            continue
        nx = max(x, min(px, x + max(0, sw - width)))
        ny = max(y, min(py, y + max(0, sh - height)))
        dist2 = (nx - px) ** 2 + (ny - py) ** 2
        choices.append((dist2, (nx, ny)))
    return min(choices, key=lambda item: item[0])[1] if choices else point


def next_monitor_position(point: Point, size: Point, screens: Sequence[Rect]) -> Point:
    """Passa ao proximo monitor real, ordenado da esquerda para a direita."""
    valid = sorted((r for r in screens if r[2] > 0 and r[3] > 0), key=lambda r: (r[0], r[1]))
    if not valid:
        return point
    midpoint = (point[0] + size[0] / 2, point[1] + size[1] / 2)

    def distance(rect: Rect) -> float:
        x, y, w, h = rect
        nx = max(x, min(midpoint[0], x + w))
        ny = max(y, min(midpoint[1], y + h))
        return (nx - midpoint[0]) ** 2 + (ny - midpoint[1]) ** 2

    current = min(range(len(valid)), key=lambda index: distance(valid[index]))
    target = valid[(current + 1) % len(valid)]
    x, y, w, h = target
    return clamp_to_screens((x + (w - size[0]) // 2, y + (h - size[1]) // 2), size, [target])


def nearest_edge_position(point: Point, size: Point, screens: Sequence[Rect]) -> Point:
    """Encosta na borda da tela real mais proxima, nao em limites virtuais."""
    if not screens:
        return point
    px, py = clamp_to_screens(point, size, screens)
    owning = min(
        (r for r in screens if r[2] > 0 and r[3] > 0),
        key=lambda r: (clamp_to_screens((px, py), size, [r])[0] - px) ** 2
        + (clamp_to_screens((px, py), size, [r])[1] - py) ** 2,
        default=None,
    )
    if owning is None:
        return point
    x, y, w, h = owning
    left, right = x + 6, x + max(0, w - size[0]) - 6
    top, bottom = y + 6, y + max(0, h - size[1]) - 6
    candidates = [(left, py), (right, py), (px, top), (px, bottom)]
    best = min(candidates, key=lambda p: (p[0] - px) ** 2 + (p[1] - py) ** 2)
    return clamp_to_screens(best, size, [owning])
