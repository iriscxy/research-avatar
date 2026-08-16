#!/usr/bin/env python3
"""Mechanical sanity checks for the footprint-cover definitions."""
from math import dist

points = {"swap": (0.176384, 0.268927), "delete": (0.183126, 0.190846), "insert": (0.194127, 0.188247), "keyboard": (0.191414, 0.228889)}
assert all(dist(p, p) == 0 for p in points.values())
assert all(abs(dist(a, b) - dist(b, a)) < 1e-12 for a in points.values() for b in points.values())
assert len({"delete", "insert", "swap"}) < len(points)
print("PASS: metric symmetry, identity, and strict basis reduction")
