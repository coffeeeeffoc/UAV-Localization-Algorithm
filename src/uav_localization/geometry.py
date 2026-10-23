"""SO(3) operations. Quaternions use SciPy's scalar-last (x, y, z, w) order."""

import numpy as np
from scipy.spatial.transform import Rotation


def skew(vector):
    """Return [v]_x, so skew(v) @ w == cross(v, w)."""
    x, y, z = np.asarray(vector, dtype=float)
    return np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]])


def right_jacobian(rotvec):
    """Exact right Jacobian of SO(3), including its small-angle limit."""
    vector = np.asarray(rotvec, dtype=float)
    theta = np.linalg.norm(vector)
    cross = skew(vector)
    if theta < 1e-5:
        return np.eye(3) - 0.5 * cross + cross @ cross / 6.0
    return (np.eye(3) - (1 - np.cos(theta)) / theta**2 * cross
            + (theta - np.sin(theta)) / theta**3 * cross @ cross)


def compose_quaternion(quaternion, rotvec):
    """Apply a right-multiplicative body-frame rotation; return unit xyzw."""
    return (Rotation.from_quat(quaternion) * Rotation.from_rotvec(rotvec)).as_quat()
